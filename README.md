# ndn-python-repo

[![Build Status](https://travis-ci.org/JonnyKong/ndn-python-repo.svg?branch=master)](https://travis-ci.org/JonnyKong/ndn-python-repo) [![PyPI version](https://badge.fury.io/py/ndn-python-repo.svg)](https://badge.fury.io/py/ndn-python-repo)

A Named Data Networking (NDN) Repo implementation using [python-ndn](https://github.com/zjkmxy/python-ndn).

## Prerequisites

* Required: Python 3.6+
* Required: [python-ndn](https://github.com/zjkmxy/python-ndn) - A Named Data Networking client library with AsyncIO support in Python 3.
* Required: [NFD](https://github.com/named-data/NFD) - Named Data Networking Forwarding Daemon

## Install & Run

Install the latest release with pip

```bash
$ /usr/bin/pip3 install ndn-python-repo
```
Optionally, you can install the latest development version from local:
```bash
$ git clone https://github.com/JonnyKong/ndn-python-repo.git
$ cd ndn-python-repo && /usr/bin/pip3 install -e .
```
Start a repo instance:

```bash
$ ndn-python-repo
```

## Configuration

Optionally, you can specify the configuration file on the command line (`ndn-python-repo -c <config_file>`). 

A sample configuration file with default configurations is provided here: [ndn-python-repo.conf.sample](ndn_python_repo/ndn-python-repo.conf.sample).

### Change the default database

The default database is sqlite3. Optionally, you can install ndn-python-repo with additional database support:

```bash
$ /usr/bin/pip3 install ndn-python-repo[leveldb]
$ /usr/bin/pip3 install ndn-python-repo[mongodb]
```

## Systemd Support

To enable systemd support, you need to install systemd scripts:
```bash
$ sudo ndn-python-repo-install
```

Then, start, stop, and monitor a repo instance with systemd:

```bash
$ sudo systemctl start ndn-python-repo
$ sudo systemctl stop ndn-python-repo
$ sudo systemctl status ndn-python-repo
```

## Migrate from repo-ng

To migrate data from repo-ng:

```bash
$ ndn-python-repo-port -d <path-to-repo-ng-dbfile> -a <ndn-python-repo-ipaddr> -p <ndn-python-repo-port>
```

