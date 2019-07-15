# NDN-Repo

A quick-and-dirty Named Data Networking (NDN) Repo, implemented using [PyNDN](https://github.com/named-data/PyNDN2).

## Prerequisites

* Required: [PyNDN](https://github.com/named-data/PyNDN2) - A Named Data Networking client library in Python
* Required: [MongoDB](https://www.mongodb.com) - A document-oriented database
* Required: [ndn-cxx ](https://github.com/named-data/ndn-cxx)- NDN C++ library with eXperimental eXtensions
* Required: [NFD](https://github.com/named-data/NFD) - Named Data Networking Forwarding Daemon
* Required: [PyMongo](https://api.mongodb.com/python/current/) - MongoDB Python interface
* Required: [Protobuf](https://developers.google.com/protocol-buffers/) - Serializing structured data

## Getting Started

For macOS and Ubuntu:

```bash
git clone https://github.com/JonnyKong/NDN-Repo.git

# Compile protobuf
cd src/command && make
cd ../..

# Start a repo instance
cd src && python3 main.py
```

