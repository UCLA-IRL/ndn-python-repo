from flask import Flask, escape, request, url_for, send_file
import logging
import subprocess
import os
import signal

app = Flask(__name__)

shell_cmd = 'python3 main.py'
p = subprocess.Popen(shell_cmd, shell=True)

"""
status() return code:
0 - running
1 - normal exit
2 - exit on error
3 - killed by signal
"""


@app.route('/status')
def status():
    if p.poll() is None:
        return '0'
    elif p.poll() == 0:
        return '1'
    elif p.poll() > 0:
        return '2'
    return '3'


"""
pid() returns subprocess (repo)'s process id
"""


@app.route('/pid')
def pid():
    return str(p.pid)


"""
stop() returns 0, a confirmation.
"""


@app.route('/stop')
def stop():
    if p.poll() is None:
        os.kill(p.pid, signal.SIGTERM)
    return '0'


"""
restart() returns 0, a confirmation.
"""


@app.route('/restart')
def restart():
    global p
    if p.poll() is None:
        os.kill(p.pid, signal.SIGTERM)
    p = subprocess.Popen(shell_cmd, shell=True)
    return '0'


@app.route('/start')
def start():
    global p
    if p.poll() is None:
        return '0' #'already running' user doesn't need to know this detail
    p = subprocess.Popen(shell_cmd, shell=True)
    return '0'


@app.route('/perform_test')
def perform_test():
    return 'not yet implemented'


def main():
    logging.info('repo daemon has been started')


if __name__ == "__main__":
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)
    app.run(host='0.0.0.0', port=9876)
    try:
        main()
    except KeyboardInterrupt:
        pass
