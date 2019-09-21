# NDN-Repo

A quick-and-dirty Named Data Networking (NDN) Repo implementation using [PyNDN](https://github.com/named-data/PyNDN2).

## Prerequisites

* Required: [PyNDN](https://github.com/named-data/PyNDN2) - A Named Data Networking client library in Python
* Required: [NFD](https://github.com/named-data/NFD) - Named Data Networking Forwarding Daemon
* Required: [Protobuf](https://developers.google.com/protocol-buffers/) - Serializing structured data
* Optional: [LevelDB](https://github.com/google/leveldb) - Fast key-value storage library
* Optional: [MongoDB](https://www.mongodb.com) - A document-oriented database
* Optional: [PyMongo](https://api.mongodb.com/python/current/) - MongoDB Python interface

## Getting Started

For macOS and Ubuntu:

```bash
git clone https://github.com/JonnyKong/NDN-Repo.git

# 1) Create virtual env
python3 -m venv ./venv
./venv/bin/python -m pip install -r requirements.txt

# 2) Compile protobuf files
cd src/command
make

# 3) Start a repo instance
./venv/bin/python main.py

# Insert a file into the repo
cd src && python3 putfile.py -r <repo_name> -f <path_to_file> -n <filename_in_repo>

# Fetch a file from the repo
cd src && python3 getfile.py -r <repo_name> -n <filename_in_repo>
```

## TODO

- [ ] Refactor: move hard-coded parts into _config.yaml
- [ ] Performance optimizations
- [ ] Insert check command
- [ ] Delete command
- [ ] Add command validator for `handles`