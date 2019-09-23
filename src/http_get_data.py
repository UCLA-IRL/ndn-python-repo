import logging
import requests
import base64
from pyndn import Data, Name
from pyndn.encoding.tlv_0_2_wire_format import Tlv0_2WireFormat

"""
by Yufeng Zhang and Zhaoning Kong

This is HTTPGetData demo. Applications can fetch NDN Data from Repo using
HTTP/HTTPS.
"""

class HTTPGetDataClient(object):
    """
    HTTPGetDataClient is used to fetch NDN Data via HTTPS.
    Applications should instantiate this class and use
    instances of this class to access Repo.
    """

    """
    argument:
    addr is the address of Repo control center.
    - do not confuse this with Repo TCP Bulk Insersion
    - uses local control center by default

    port is the TCP port used by the control center.
    - 1234 by default
    """

    def __init__(self, addr:str='127.0.0.1', port: str='1234'):
        self.addr = addr
        self.port = port
        logging.info('HTTPGetDataClient instance has been created. Repo address: {}:{}'.format(addr, port))

    """
    get_data() takes a Data name and fetches that Data from the Repo.
    It returns the Data from the Repo on success
    Returns None on error, e.g. HTTP connection error, Data doesn't exist, etc.
    """

    def get_data(self, data_name : str):
        base64_data_name = base64.b64encode(str.encode(data_name)).decode()
        data_url = 'http://{}:{}/download/{}'.format(self.addr, self.port, base64_data_name)
        logging.info('HTTPGetDataClient instance begin to request data with url {}'.format(data_url))

        try:
            data_blob = requests.get(data_url).content
        except:
            logging.warning('HTTP network failure when trying to download Data with name {}'.format(data_name))
            return None # should I raise an Error here?

        data = Data()
        decoder = Tlv0_2WireFormat()

        try:
            decoder.decodeData(data, data_blob, False)
        except ValueError:
            logging.warning('Requested data with name {} : Decode failed.'.format(data_name))
            print(data_blob)
            return None

        return data

def main():
    client = HTTPGetDataClient() # by default, use control center on local machine

    data = client.get_data('/ndn/poksaeeebu/qoaaooyujl')
    if data is None:
        logging.warning('Data cannot be fetched.')
        return
    print(data.name)
    print(data.content)

if __name__ == '__main__':
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)
    main()
