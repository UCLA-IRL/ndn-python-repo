# NDN-Repo

A quick-and-dirty Named Data Networking (NDN) Repo implementation using [PyNDN](https://github.com/named-data/PyNDN2).

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

# Compile protobuf files
cd src/command
make
cd ../..

# Start a repo instance
cd src && python3 main.py

# Insert a file into the repo
cd src && python3 putfile.py -r <repo_name> -f <path_to_file> -n <filename_in_repo>

# Fetch a file from the repo
cd src && python3 getfile.py -r <repo_name> -n <filename_in_repo>
```

## TODO

- [ ] Refactor: move hard-coded parts into _config.yaml
- [ ] Performance optimizations