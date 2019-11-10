# NDN-Repo

A quick-and-dirty Named Data Networking (NDN) Repo implementation using [python-ndn](https://github.com/zjkmxy/python-ndn).

## Prerequisites

* Required: Python 3.6+
* Required: [python-ndn](https://github.com/zjkmxy/python-ndn) - A Named Data Networking client library with AsyncIO support in Python 3.
* Required: [NFD](https://github.com/named-data/NFD) - Named Data Networking Forwarding Daemon
* Optional: The default backend database is SQLite3. If you want to change the default database, you need one of:
  * [LevelDB](https://github.com/google/leveldb) - Fast key-value storage library
  * [MongoDB](https://www.mongodb.com) - A document-oriented database, and [PyMongo](https://api.mongodb.com/python/current/) - MongoDB Python interface

## Getting Started

For macOS and Ubuntu:

```bash
git clone https://github.com/JonnyKong/NDN-Repo.git

# 1) Create virtual env
python3 -m venv ./venv
./venv/bin/python -m pip install -r requirements.txt
source ./venv/bin/activate

# 2) Compile protobuf files
cd src/command
make

# 3) Start a repo instance
python main.py

# Insert a file into the repo
cd src/clients && python putfile.py -r <repo_name> -f <path_to_file> -n <filename_in_repo>

# Fetch a file from the repo
cd src/clients && python getfile.py -r <repo_name> -n <filename_in_repo>
```

## TODO

- [x] TCP Bulk Insertion functionality, tested using NDNCERT
- [x] Control Center basic Web interface
- [x] Control Center backend: list Data, delete Data, display up-to-date Repo status, commands (stop, start, restart)
- [x] HTTP Get Data Demo program (http_get_data.py in directory `src`)
- [x] Add an instructions page
- [x] Insert check command
- [x] Delete command
- [x] Delete check command
- [ ] Add command validator for `handles`
- [ ] Finalize database implementation for Google Cloud DataStore. (MongoDB is not very convenient to configure)
- [ ] Now we have HTTP get Data endpoint. We might want to add a TCP get Data. This introduces design questions, e.g. Do we use port 7376 for Data fetching, or we use a different port?
- [ ] Configure a PyNDN-Repo Docker for easier deployment
- [ ] Nail down protocol design
- [ ] Implement Trust Schema for Data and command verification
- [ ] Add more demo programs, and improve documentations

## Quick Start: Use Repo Control Center

1. Download and start MongoDB Daemon. You can download it [here](https://www.mongodb.com/download-center/community)

```bash
Ubuntu:bin yufengzh$ sudo ./mongod
```

2. Start repo-daemon, which will automatically start Repo

```bash
Ubuntu:dev yufengzh$ cd NDN-Repo/
Ubuntu:NDN-Repo yufengzh$ source venv/bin/activate
(venv) Ubuntu:NDN-Repo yufengzh$ python repo_daemon.py

```

3. Start control-center

```bash
(venv) Ubuntu:NDN-Repo yufengzh$ python control_center.py
```

4. Go to control center http://localhost:1234 on your Web browser, where you can add dummy Data, see what Data is in the Repo, delete Data, start/stop/restart Repo, test Repo, etc.

### 
