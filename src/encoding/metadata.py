# -*- coding: utf-8 -*-
"""
    NDN Repo metadata.
    Repo and data producer negoatiate on metadata. Metadata is transparent to user (command issuer).
    @Author jonnykong@cs.ucla.edu

    @Date   2019-08-28
"""

class MetaData(object):

    TYPE_NORMAL = 1         # Dataset has only one data 
    TYPE_SEQUENTIAL = 2     # Dataset use sequence numbers as naming convention
    TYPE_LINKED = 3         # Each data contain name to prev/next data 
    TYPE_TRIGGERED = 4      # Repo should use long-lived interest

    def __init__(self):
        # Data type is one of NORMAL, SEQUENTIAL, LINKED, or TRIGGERED
        self.data_type = None
        
        # If SEQUENTIAL, start and end sequence of data. If end is not known, repo will keep probing
        # the next data until failure count reach some threshold
        self.seq_start = None
        self.seq_end = None
        
        # If LINKED, the name of first data. This is required because repo need a starting point to
        # traverse the linked list
        self.first_name = None