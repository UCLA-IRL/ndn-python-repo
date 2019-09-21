import urllib
import plyvel
import os
from src import *
from flask import Flask, escape, request, url_for
from flask import render_template

class ControlCenterLevelDBStorage(object):
    def __init__(self, dir: str):
        db_dir = os.path.expanduser(dir)  # change to absolute path
        self.db = plyvel.DB(db_dir, create_if_missing=True)

    def put(self, key: str, value: bytes):
        self.db.put(key.encode(), value)

    def get(self, key: str) -> bytes:
        return self.db.get(key.encode())

    def exists(self, key: str) -> bool:
        ret = self.db.get(key.encode())
        if ret:
            return True
        else:
            return False

    def remove(self, key: str) -> bool:
        self.db.delete(key.encode())
        return True

    def get_key_list(self) -> list:
        key_list = list()
        for key, value in self.db:
            key_list.append(key.decode())
        return key_list

app = Flask(__name__)

config = get_yaml()
dire = config['db_config']['leveldb']['dir']
controlCenterDB = ControlCenterLevelDBStorage(dire)

@app.route('/')
def home():
    encoded_key_list = list()
    for item in controlCenterDB.get_key_list():
        encoded_key_list.append((item, urllib.parse.quote(item, safe='')))
    return render_template('home.html', key_list=encoded_key_list)