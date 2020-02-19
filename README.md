# ndn-python-repo

[![Build Status](https://travis-ci.org/JonnyKong/ndn-python-repo.svg?branch=master)](https://travis-ci.org/JonnyKong/ndn-python-repo)

A Named Data Networking (NDN) Repo implementation using [python-ndn](https://github.com/zjkmxy/python-ndn).

## Prerequisites

* Required: Python 3.6+
* Required: [python-ndn](https://github.com/zjkmxy/python-ndn) - A Named Data Networking client library with AsyncIO support in Python 3.
* Required: [NFD](https://github.com/named-data/NFD) - Named Data Networking Forwarding Daemon
* Optional: The default backend database is SQLite3. If you want to change the default database, you need one of:
  * [LevelDB](https://github.com/google/leveldb) - Fast key-value storage library
  * [MongoDB](https://www.mongodb.com) - A document-oriented database, and [PyMongo](https://api.mongodb.com/python/current/) - MongoDB Python interface

## Install & Run

Install the latest release with pip

```bash
$ sudo /usr/bin/pip3 install ndn-python-repo
```
Optionally, you can install the latest development version from local:
```bash
$ git clone https://github.com/JonnyKong/ndn-python-repo.git
$ cd ndn-python-repo && sudo /usr/bin/pip3 install -e .
```
Install systemd scripts:
```bash
$ sudo ndn-python-repo-install
```
Start a repo instance:

```bash
$ ndn-python-repo
```

## Configuration

Optionally, you can specify the configuration file on the command line (`ndn-python-repo -c <config_file>`). 

A sample configuration file with default configurations is provided here: [ndn-python-repo.conf.sample](ndn_python_repo/ndn-python-repo.conf.sample).

## Systemd Support

Start, stop and monitor a repo instance with systemd:

```bash
$ sudo systemctl start ndn-python-repo
$ sudo systemctl stop ndn-python-repo
$ sudo systemctl status ndn-python-repo
```
