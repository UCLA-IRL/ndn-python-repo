# -----------------------------------------------------------------------------
# Passive SVS Listener.
#
# @Author tianyuan@cs.ucla.edu
# @Date   2024-03-29
# -----------------------------------------------------------------------------

import logging
from base64 import b64decode, b64encode
from typing import Callable
from ndn.app import NDNApp
from ndn.app_support.svs import StateVecWrapper, SvsState
from ndn.encoding import Name, NonStrictName, DecodeError, FormalName, BinaryStr, InterestParam, parse_interest, \
    parse_tl_num, UintField
from ndn.encoding.ndn_format_0_3 import TypeNumber
from ndn.utils import gen_nonce

OnMissingDataFunc = Callable[["PassiveSvs"], None]
r"""
Called when there is a missing event.
MUST BE NON-BLOCKING. Therefore, it is not allowed to fetch the missing data in this callback.
It can start a task or trigger a signal to fetch missing data.
"""


class PassiveSvs:
    base_prefix: FormalName
    on_missing_data: OnMissingDataFunc

    local_sv: dict[bytes, int]
    state: SvsState
    running: bool
    ndn_app: NDNApp | None

    def __init__(self, base_prefix: NonStrictName,
                 on_missing_data: OnMissingDataFunc):
        self.base_prefix = Name.normalize(base_prefix)
        self.on_missing_data = on_missing_data
        self.local_sv = {}
        self.inst_buffer = {}
        self.state = SvsState.SyncSteady
        self.running = False
        self.ndn_app = None
        self.logger = logging.getLogger(__name__)

    def encode_into_states(self):
        states = {}
        inst_buffer_enc = {}
        for nid, inst in self.inst_buffer.items():
            inst_buffer_enc[nid] = b64encode(inst).decode('utf-8')
        states['local_sv'] = self.local_sv
        states['inst_buffer'] = inst_buffer_enc
        return states

    def decode_from_states(self, states: dict):
        inst_buffer_dec = {}
        for nid, inst in states['inst_buffer'].items():
            inst_buffer_dec[nid] = b64decode(inst)
        self.local_sv = states['local_sv']
        self.inst_buffer = inst_buffer_dec

    def send_interest(self, interest_wire):
        final_name, interest_param, _, _ = parse_interest(interest_wire)
        interest_param.nonce = gen_nonce()
        # a bit hack, refresh the nonce and re-encode
        wire_ptr = 0
        while wire_ptr + 5 < len(interest_wire):
            typ, typ_len = parse_tl_num(interest_wire[wire_ptr:], 0)
            size, siz_len = parse_tl_num(interest_wire[wire_ptr:], typ_len)
            if typ != TypeNumber.NONCE or typ_len != 1 or \
                    size != 4 or siz_len != 1:
                wire_ptr += 1
                continue
            else:
                # that's it!
                wire = bytearray(interest_wire)
                nonce = UintField(TypeNumber.NONCE, fixed_len=4)
                markers = {}
                nonce.encoded_length(interest_param.nonce, markers)
                nonce.encode_into(interest_param.nonce, markers, wire, wire_ptr)
                break
        logging.info(f'Sending buffered interest: {Name.to_str(final_name)}')
        # do not await for this
        self.ndn_app.express_raw_interest(final_name, interest_param, wire)

    def sync_handler(self, name: FormalName, _param: InterestParam, _app_param: BinaryStr | None,
                     raw_packet: BinaryStr) -> None:
        if len(name) != len(self.base_prefix) + 2:
            logging.error(f'Received invalid Sync Interest: {Name.to_str(name)}')
            return
        _, _, _, sig_ptrs = parse_interest(raw_packet)
        sig_info = sig_ptrs.signature_info
        if sig_info and sig_info.key_locator and sig_info.key_locator.name:
            logging.info(f'Received Sync Interest: {Name.to_str(sig_info.key_locator.name)}')
        else:
            logging.info(f'Drop unsigned or improperly signed Sync Snterests')
            return
        try:
            remote_sv_pkt = StateVecWrapper.parse(name[-2]).val
        except (DecodeError, IndexError) as e:
            logging.error(f'Unable to decode state vector [{Name.to_str(name)}]: {e}')
            return
        if remote_sv_pkt is None:
            logging.error(f'Sync Interest does not contain state vectors')
            return
        remote_sv = remote_sv_pkt.entries

        # No lock is needed since we do not await
        # Compare state vectors
        rsv_dict = {}
        for rsv in remote_sv:
            if not rsv.node_id:
                continue
            rsv_id = Name.to_str(rsv.node_id)
            rsv_seq = rsv.seq_no
            rsv_dict[rsv_id] = rsv_seq

        need_fetch = False
        for rsv_id, rsv_seq in rsv_dict.items():
            already_sent = []
            lsv_seq = self.local_sv.get(rsv_id, 0)
            if lsv_seq < rsv_seq:
                # Remote is latest
                need_fetch = True
                self.local_sv[rsv_id] = rsv_seq
                self.logger.debug(f'Missing data for: [{Name.to_str(rsv_id)}]: {lsv_seq} < {rsv_seq}')
                self.inst_buffer[rsv_id] = raw_packet
            elif lsv_seq > rsv_seq:
                # Local is latest
                self.logger.debug(f'Outdated remote on: [{Name.to_str(rsv_id)}]: {rsv_seq} < {lsv_seq}')
                if rsv_id in self.inst_buffer:
                    raw_inst = self.inst_buffer[rsv_id]
                else: raw_inst = None
                if raw_inst and raw_inst not in already_sent:
                    already_sent.append(raw_inst)
                    self.send_interest(raw_inst)
                else: pass

        # Notify remote there are missing nodes
        diff = self.local_sv.keys() - rsv_dict.keys()
        if len(diff) > 0:
            self.logger.info(f'Remote missing nodes: {list(diff)}')
            # Missing nodes may only exist in other nodes' sync interest,
            # therefore we have to send all buffered sync interest out,
            # unless they were sent before.
            already_sent = []
            for _, raw_inst in self.inst_buffer.items():
                if raw_inst not in already_sent:
                    already_sent.append(raw_inst)
                    self.send_interest(raw_inst)
        if need_fetch:
            self.on_missing_data(self)

    def start(self, ndn_app: NDNApp):
        if self.running:
            raise RuntimeError(f'Sync is already running @[{Name.to_str(self.base_prefix)}]')
        self.running = True
        self.ndn_app = ndn_app
        self.ndn_app.route(self.base_prefix, need_raw_packet=True)(self.sync_handler)

    async def stop(self):
        if not self.running:
            return
        self.running = False
        await self.ndn_app.unregister(self.base_prefix)
        self.logger.info("Passive SVS stopped.")
