import logging
import random
import string
from src import *
from flask import Flask, escape, request, url_for, send_file
from flask import render_template
import datetime
import base64
import uuid
import io
from pyndn import Data, Name
import requests

# """
# control_center_state
# member variable:
# status, DB instance
#
# """
#
#
# class ControlCenterState(object):
#     def __init__(self, dbInstance: Storage):
#         self.status = 'RUNNING'
#         self.dbInstance = dbInstance


app = Flask(__name__)

config = get_yaml()
# dire = config['db_config']['leveldb']['dir']
# controlCenterDB = LevelDBStorage(dire)
# control_center_state = ControlCenterState(controlCenterDB)
controlCenterDB = MongoDBStorage(config['db_config']['mongodb']['db'], config['db_config']['mongodb']['collection'])


def main():
    logging.info('repo control center has been started')


if __name__ == "__main__":
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)
    try:
        main()
    except KeyboardInterrupt:
        pass


@app.route('/')
def home():
    repo_status = requests.get('http://127.0.0.1:9876/status').content.decode()
    """
    status() return code:
    0 - running
    1 - normal exit
    2 - exit on error
    3 - killed by signal
    """
    if repo_status == '0':
        status_tag = 'success'
        status_message = 'running'
    elif repo_status == '1':
        status_tag = 'warning'
        status_message = 'normal exit'
    elif repo_status == '2':
        status_tag = 'danger'
        status_message = 'exit on error'
    else:
        status_tag = 'danger'
        status_message = 'killed by signal'

    encoded_key_list = list()
    number_keys = 0
    for item in controlCenterDB.get_key_list():
        if item == 'prefixes':
            continue
        encoded_key_list.append((item, base64.b64encode(str.encode(item)).decode()))
        number_keys += 1
    return render_template('home.html', key_list=encoded_key_list, number_keys=number_keys,
                           status_tag=status_tag, status_message=status_message)


@app.route('/delete/<path:data_name_base64>')
def delete_data(data_name_base64=None):
    data_name = base64.b64decode(data_name_base64).decode()
    error_message = None

    if not controlCenterDB.exists(data_name):
        return render_template('message.html',
                               title='Error',
                               heading='Data does not exist',
                               message='The requested data to be deleted with name {} does not exist in the repo.'
                               .format(data_name),
                               time=datetime.datetime.now(),
                               badge_tag='danger',
                               alert_tag='danger',
                               badge_text='failed')

    controlCenterDB.remove(data_name)

    return render_template('message.html',
                           title='Success',
                           heading='Success',
                           message='Data with name {} has been deleted.'.format(data_name),
                           time=datetime.datetime.now(),
                           badge_tag='success',
                           alert_tag='success',
                           badge_text='OK')


def random_string(stringLength=10):
    """Generate a random string of fixed length """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))


@app.route('/insert_fake_data')
def insert_fake_data():
    i = 0
    while i < 10:
        i += 1
        fake_data = Data(Name('/ndn/' + random_string() + '/' + random_string()))
        fake_data.setContent(random_string(100))
        controlCenterDB.put(fake_data.name.__str__(), fake_data.wireEncode().toBytes())

    return render_template('message.html',
                           title='Success',
                           heading='Success',
                           message='Ten fake Data packets have been inserted into the repo',
                           time=datetime.datetime.now(),
                           badge_tag='success',
                           alert_tag='success',
                           badge_text='OK')


@app.route('/delete-all')
def delete_all_data():
    for key, value in controlCenterDB.db:
        controlCenterDB.remove(key.decode())
    return render_template('message.html',
                           title='Success',
                           heading='Success',
                           message='All data packets in the repo have been removed',
                           time=datetime.datetime.now(),
                           badge_tag='success',
                           alert_tag='success',
                           badge_text='OK')


@app.route('/download/<path:data_name_base64>')
def download_data(data_name_base64=None):
    data_name = base64.b64decode(data_name_base64).decode()
    error_message = None
    if not controlCenterDB.exists(data_name):
        return render_template('message.html',
                               title='Error',
                               heading='Data does not exist',
                               message='The requested data to download with name {} does not exist in the repo.'
                               .format(data_name),
                               time=datetime.datetime.now(),
                               badge_tag='danger',
                               alert_tag='danger',
                               badge_text='failed')
    data_bytes = controlCenterDB.get(data_name)
    result = send_file(
        io.BytesIO(data_bytes),
        attachment_filename=str(uuid.uuid4()),
        mimetype='application/octet-stream',
        as_attachment=True
    )
    result.headers["x-suggested-filename"] = str(uuid.uuid4())
    return result
