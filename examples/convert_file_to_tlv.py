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

app = NDNApp()
def _create_packets(name, data, freshness_period, final_block_id):
    packet = app.prepare_data(name, data, freshness_period=freshness_period, final_block_id=final_block_id)
    return packet

def main():
    """Convert a file into tlv packets. Store them in the output file one 
    after the other that can be dumped into an NDN repo using netcat"""
    
    cpu_count = multiprocessing.cpu_count()
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--name', type=str, required=True)
    parser.add_argument('-i', '--input_file', type=str, required=True)
    parser.add_argument('-o', '--output_file', type=str, required=True)
    parser.add_argument('-s', '--segment_size', type=int, default=8000, required=False)
    parser.add_argument('-f', '--freshness_period', type=int, default=0, required=False) #always stale
    parser.add_argument('-c', '--cpu_count', type=int, default=cpu_count, required=False)

    args = parser.parse_args()

    logging.basicConfig(format='[{asctime}]{levelname}:{message}',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO,
                        style='{')

    segment_size = args.segment_size
    name = Name.normalize(args.name)
    name.append(Component.from_version(timestamp()))

    print("Converting {} into tlv packets and storing in {} \nSegment size = {}, Freshness Period = {}, CPU_Count = {}"
            .format(args.input_file, args.output_file, args.segment_size, args.freshness_period, args.cpu_count))


    with open(args.input_file, 'rb') as infile, open(args.output_file, 'wb') as outfile:
        data = infile.read()
        seg_cnt = (len(data) + segment_size - 1) // segment_size
        freshness_period = args.freshness_period
        final_block_id = Component.from_segment(seg_cnt-1)
        packets = [[name + [Component.from_segment(i)], data[i*segment_size:(i+1)*segment_size], 
            freshness_period, final_block_id] 
            for i in range(seg_cnt)]
        with multiprocessing.Pool(processes=args.cpu_count) as p:
            res = p.starmap(_create_packets, packets)
            packet_list = res
        num_packets = len(packet_list)
        print('Created {} chunks under name {}'.format(num_packets, args.name))
        for encoded_packet in packet_list:
            outfile.write(encoded_packet)
        print("written {} packets to file {}".format(num_packets, args.output_file))
        print("You can use  \"nc localhost 7376 < {}\" to load data into the repo".format(args.output_file))

if __name__ == '__main__':
    main()
