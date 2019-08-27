# NDN-Repo

A quick-and-dirty Named Data Networking (NDN) Repo implementation using [PyNDN](https://github.com/named-data/PyNDN2).

## Prerequisites

* Required: [PyNDN](https://github.com/named-data/PyNDN2) - A Named Data Networking client library in Python
* Required: [MongoDB](https://www.mongodb.com) - A document-oriented database
* Required: [ndn-cxx](https://github.com/named-data/ndn-cxx)- NDN C++ library with eXperimental eXtensions
* Required: [NFD](https://github.com/named-data/NFD) - Named Data Networking Forwarding Daemon
* Required: [Protobuf](https://developers.google.com/protocol-buffers/) - Serializing structured data
* Optional: [PyMongo](https://api.mongodb.com/python/current/) - MongoDB Python interface
* Optional: [LevelDB](https://github.com/google/leveldb) - Fast key-value storage library

## Getting Started

For macOS and Ubuntu:

```bash
git clone https://github.com/JonnyKong/NDN-Repo.git

# Compile protobuf files
cd src/command
make

# Start a repo instance
cd src && python3 main.py

# Insert a file into the repo
cd src && python3 putfile.py -r <repo_name> -f <path_to_file> -n <filename_in_repo>

# Fetch a file from the repo
cd src && python3 getfile.py -r <repo_name> -n <filename_in_repo>
```

## TODO

- [ ] Performance optimizations
- [ ] Insert check command
- [ ] Delete command
- [ ] Add command validator for handles
- [ ] Controller hot start