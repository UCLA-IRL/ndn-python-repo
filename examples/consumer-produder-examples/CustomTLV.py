from ndn.encoding import *

class Model(TlvModel):
    consumer_cert = BytesField(0x01)
    producer_cert = BytesField(0x02)