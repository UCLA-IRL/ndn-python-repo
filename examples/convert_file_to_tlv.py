# -----------------------------------------------------------------------------
# Copyright (C) 2019-2020 Xinyu Ma, Susmit Shannigrahi
#
# This file is part of python-ndn.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# -----------------------------------------------------------------------------
import logging
import sys
from ndn.utils import timestamp
from ndn.app import NDNApp
from ndn.encoding import Name, Component
import multiprocessing
import argparse

#CPU_COUNT = multiprocessing.cpu_count() #they aren't used, just for testing
#CPU_COUNT=1
SEGMENT_SIZE = 8000 #this should be decided at runtime

app = NDNApp()
def _create_packets(name, data, freshness_period, final_block_id):
    packet = app.prepare_data(name, data, freshness_period=freshness_period, final_block_id=final_block_id)
    return packet


def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--name', type=str, required=True)
    parser.add_argument('-i', '--input-file',type=str, required=True)
    parser.add_argument('-o', '--output-file',type=str, required=True)

    args = parser.parse_args()
    ndn_name = args.name
    input_file = args.input_file
    output_file = args.output_file

    logging.basicConfig(format='[{asctime}]{levelname}:{message}',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO,
                        style='{')

    name = Name.normalize(ndn_name)
    name.append(Component.from_version(timestamp()))

    with open(input_file, 'rb') as f, open(output_file, 'wb') as w:
        data = f.read()
        seg_cnt = (len(data) + SEGMENT_SIZE - 1) // SEGMENT_SIZE
        freshness_period = 0 #long lived data, this should really be in a config file
        final_block_id = Component.from_segment(seg_cnt-1)
        packets = [[name + [Component.from_segment(i)], data[i*SEGMENT_SIZE:(i+1)*SEGMENT_SIZE], freshness_period, final_block_id] for i in range(seg_cnt)]
        with multiprocessing.Pool(processes=None) as p: #you can also pass CPU_COUNT, None = system CPU count
            res = p.starmap(_create_packets, packets)
            packet_list = res
        num_packets = len(packet_list)
        print('Created {} chunks under name {}'.format(num_packets, ndn_name))
        for i in packet_list:
            w.write(i)
        print("written {} packets to file {}".format(num_packets,output_file))
        print("You can use  \"nc localhost 7376 < filename\" to load data into the repo")
    

if __name__ == '__main__':
    main()
