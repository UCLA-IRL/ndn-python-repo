import logging

import requests

from flask import Flask, escape, request, url_for
from flask import render_template, make_response
from src import config
from src import MongoDBStorage

import random
import string
import datetime
import base64
import uuid
import io
from pyndn import Data, Name
import pickle

app = Flask(__name__)

config = config.get_yaml()
daemon_address = 'http://' + config['repo_daemon']['addr'] + ':' + config['repo_daemon']['port'] + '/'

def connectivity_error():
    #return 'database connectivity error'
    return render_template('message.html',
                    title='Error',
                    heading='Operation failed',
                    message='Failed to connect to database. Check for connectivity.',
                    time=datetime.datetime.now(),
                    badge_tag='danger',
                    alert_tag='danger',
                    badge_text='failed')
@app.route('/')
def home():
    # r = urllib.request.urlopen('https://google.com/')
    # repo_status = r.read()
    try:
        repo_status = requests.get(daemon_address + 'status').content
        """
            status() return code:
            0 - running
            1 - normal exit
            2 - exit on error
            3 - killed by signal
        """
        if repo_status == b'0':
            status_tag = 'success'
            status_message = 'running'
        elif repo_status == b'1':
            status_tag = 'warning'
            status_message = 'normal exit'
        elif repo_status == b'2':
            status_tag = 'danger'
            status_message = 'exit on error'
        elif repo_status == b'3':
            status_tag = 'danger'
            status_message = 'killed by signal'
        else:
            status_tag = 'danger'
            status_message = 'failed to connect to daemon'
    except:
        logging.info('error when getting repo status from daemon via HTTP')
        status_tag = 'danger'
        status_message = 'failed to connect to daemon'

    encoded_key_list = list()
    number_keys = 0

    try:
        for item in controlCenterDB.keys():
            if item == 'prefixes':
                continue
            is_cert = "/KEY/" in item
            encoded_key_list.append((is_cert, item, base64.b64encode(str.encode(item)).decode()))
            number_keys += 1
    except:
        return connectivity_error()

    return render_template('home.html', key_list=encoded_key_list, number_keys=number_keys,
                           status_tag=status_tag, status_message=status_message)

def execute_command(command: str):
    try:
        execution_status = requests.get(daemon_address + command).content
        if execution_status == b'0':
            return render_template('message.html',
                            title='Success',
                            heading='Success',
                            message= 'command {} executed successfully.'.format(command),
                            time=datetime.datetime.now(),
                            badge_tag='success',
                            alert_tag='success',
                            badge_text='OK')
    except:
            return connectivity_error()

    return render_template('message.html',
                    title='Error',
                    heading='Operation failed',
                    message='Unknown return code from daemon.',
                    time=datetime.datetime.now(),
                    badge_tag='danger',
                    alert_tag='danger',
                    badge_text='failed')

@app.route('/stop')
def stop():
    return execute_command('stop')

@app.route('/start')
def start():
    return execute_command('start')

@app.route('/restart')
def restart():
    return execute_command('restart')

@app.route('/delete/<path:data_name_base64>')
def delete_data(data_name_base64=None):
    data_name = base64.b64decode(data_name_base64).decode()

    try:
        exist = controlCenterDB.exists(data_name)
    except:
        return connectivity_error()

    if not exist:
        return render_template('message.html',
                                title='Error',
                                heading='Data does not exist',
                                message='The requested data to be deleted with name {} does not exist in the repo.'
                                .format(data_name),
                                time=datetime.datetime.now(),
                                badge_tag='danger',
                                alert_tag='danger',
                                badge_text='failed')
    try:
        controlCenterDB.remove(data_name)
    except:
        return connectivity_error()

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
        try:
            controlCenterDB.put(fake_data.name.__str__(), fake_data.wireEncode().toBytes())
        except:
            return connectivity_error()

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
    try:
        for key in controlCenterDB.get_key_list():
            controlCenterDB.remove(key) # TODO: this is ok with mongo;
                                    # need key.decode() with LevelDBStorage
                                    # but no need to worry
                                    # cc doesn't support LevelDBStorage
                                    # just a note for future compatibility
    except:
        return connectivity_error()

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
    is_cert = request.args.get('certificate', default=False, type=bool)
    is_base64 = request.args.get('base64', default=False, type=bool)
    data_name = base64.b64decode(data_name_base64).decode()
    try:
        exist = controlCenterDB.exists(data_name)
    except:
        return connectivity_error()

    if not exist:
        return render_template('message.html',
                               title='Error',
                               heading='Data does not exist',
                               message='The requested data to download with name {} does not exist in the repo.'
                               .format(data_name),
                               time=datetime.datetime.now(),
                               badge_tag='danger',
                               alert_tag='danger',
                               badge_text='failed')
    try:
        data_bytes = pickle.loads(controlCenterDB.get(data_name))
    except:
        return connectivity_error()
    if is_cert:
        #cert handler
        return render_template('cert_export.html',
                               title='Certificate Export - {}'.format(data_name),
                               cert_name=data_name,
                               cert_base64=base64.b64encode(data_bytes).decode(),
                               time=datetime.datetime.now(),
                               base64_cert_name=data_name_base64,
                               badge_tag='success',
                               alert_tag='success',
                               badge_text='ok')

    if is_base64:
        response = make_response(base64.b64encode(data_bytes).decode())
    else:
        response = make_response(data_bytes)
    response.headers.set('Content-Type', 'application/octet-stream')
    response.headers["x-suggested-filename"] = str(uuid.uuid4())
    return response

try:
    controlCenterDB = MongoDBStorage(config['db_config']['mongodb']['db'], config['db_config']['mongodb']['collection'])
except:
    logging.warning('Failed to connect to database. abort()')
    exit(1)

def main():
    logging.info('repo control center has been started')
    app.run(host='0.0.0.0', port=1234)

if __name__ == "__main__":
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)
    try:
        main()
    except KeyboardInterrupt:
        pass
