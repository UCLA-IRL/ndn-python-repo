# NDN-Repo

A Named Data Networking (NDN) Repo implementation using [python-ndn](https://github.com/zjkmxy/python-ndn).

## Prerequisites

* Required: Python 3.6+
* Required: [python-ndn](https://github.com/zjkmxy/python-ndn) - A Named Data Networking client library with AsyncIO support in Python 3.
* Required: [NFD](https://github.com/named-data/NFD) - Named Data Networking Forwarding Daemon
* Optional: The default backend database is SQLite3. If you want to change the default database, you need one of:
  * [LevelDB](https://github.com/google/leveldb) - Fast key-value storage library
  * [MongoDB](https://www.mongodb.com) - A document-oriented database, and [PyMongo](https://api.mongodb.com/python/current/) - MongoDB Python interface

## Installation

Install in user directory (without systemd):

```bash
# 1) Install the latest release with pip:
$ pip3 install NDN-Repo
# Optionally, you can install the latest development version from local:
$ git clone https://github.com/JonnyKong/NDN-Repo.git
$ cd NDN-Repo && pip3 install -e .

# 2) Start a repo instance:
$ ndn-python-repo
```

Install in system directory with systemd support:

``````bash
# 1) Install the latest release with pip
$ sudo /usr/bin/pip3 install NDN-Repo
# Optionally, you can install the latest development version from local:
$ git clone https://github.com/JonnyKong/NDN-Repo.git
$ cd NDN-Repo && sudo /usr/bin/pip3 install -e .

# 2) Install systemd script
$ ndn-python-repo-install

# 3) Start, stop and monitor a repo instance with systemd
$ sudo systemctl start ndn-python-repo
$ sudo systemctl stop ndn-python-repo
$ sudo systemctl status ndn-python-repo
``````

## TODO

- [ ] Add command validator for `handles`
- [ ] Configure a PyNDN-Repo Docker for easier deployment
- [ ] Implement Trust Schema for Data and command verification
