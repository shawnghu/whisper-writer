import argparse
import os
import socket
import sys
import subprocess
import time
from dotenv import load_dotenv

print('Starting WhisperWriter...')
load_dotenv()

parser = argparse.ArgumentParser(description='WhisperWriter')
parser.add_argument('--server', action='store_true',
                    help='Run as transcription server on localhost:47892 (for use on the GPU machine)')
parser.add_argument('--remote', action='store_true',
                    help='Send audio to remote transcription server at localhost:47892 via SSH tunnel to gratitude')
args = parser.parse_args()

if args.server:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    import uvicorn
    from server import app
    uvicorn.run(app, host='127.0.0.1', port=47892)
else:
    env = os.environ.copy()
    if args.remote:
        env['WW_USE_REMOTE'] = '1'
        print('Starting SSH tunnel to gratitude...')
        tunnel = subprocess.Popen(
            ['ssh', '-N', '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3',
             '-o', 'BatchMode=yes', '-L', '47892:localhost:47892', 'gratitude'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                with socket.create_connection(('127.0.0.1', 47892), timeout=1):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            tunnel.terminate()
            print('Error: could not connect to transcription server on gratitude after 15s — is it running?')
            sys.exit(1)
        print('Tunnel up.')

    try:
        subprocess.run([sys.executable, os.path.join('src', 'main.py')], env=env)
    finally:
        if args.remote:
            tunnel.terminate()
