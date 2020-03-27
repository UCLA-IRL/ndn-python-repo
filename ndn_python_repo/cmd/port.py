"""
    This script ports sqlite db file from repo-ng to ndn-python-repo.
    It takes as input a repo-ng sqlite database file, traverse the database and inserts data to
    an ndn-python-repo using TCP bulk insertion.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-12-26
"""

import argparse
import asyncio as aio
import os
import sqlite3
import sys
from ndn.encoding import Name, Component, ndn_format_0_3, tlv_var


def create_sqlite3_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Exception as e:
        print(e)
    return conn


def convert_name(name: bytes) -> str:
    """
    Convert the name to print.
    """
    # Remove ImplicitSha256DigestComponent TLV
    data_bytes = name[:-34]    

    # Prepend TL of Name
    type_len = tlv_var.get_tl_num_size(ndn_format_0_3.TypeNumber.DATA)
    len_len = tlv_var.get_tl_num_size(len(data_bytes))
    buf = bytearray(type_len + len_len + len(data_bytes))
    offset = 0
    offset += tlv_var.write_tl_num(ndn_format_0_3.TypeNumber.NAME, buf, offset)
    offset += tlv_var.write_tl_num(len(data_bytes), buf, offset)
    buf[offset:] = data_bytes

    # Convert bytes to URI format
    name = Name.from_bytes(buf)
    return Name.to_str(name)


async def port_over_tcp(src_db_file: str, dest_addr: str, dest_port: str):
    conn_from = create_sqlite3_connection(src_db_file)
    reader, writer = await aio.open_connection(dest_addr, dest_port)

    # Read from source database
    cur = conn_from.cursor()
    cur.execute('SELECT name, data FROM NDN_REPO_V2')
    rows = cur.fetchall()
    for row in rows:
        print('Porting data:', convert_name(row[0]))
        writer.write(row[1])
    
    writer.close()
    conn_from.close()


def main() -> int:
    parser = argparse.ArgumentParser(description='port')
    parser.add_argument('-d', '--dbfile',
                        required=True, help='Source database file')
    parser.add_argument('-a', '--addr',
                        required=True, help='IP address of python repo')
    parser.add_argument('-p', '--port',
                        required=True, help='Port of python repo')
    args = parser.parse_args()

    if args.addr == None:
        args.addr = '127.0.0.1'
    if args.port == None:
        args.addr = '7376'
    
    src_db_file = os.path.expanduser(args.dbfile)
    aio.get_event_loop().run_until_complete(port_over_tcp(src_db_file, args.addr, args.port))
    return 0


if __name__ == '__main__':
    sys.exit(main())