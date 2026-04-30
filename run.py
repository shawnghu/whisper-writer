import argparse
import os
import sys
import subprocess
from dotenv import load_dotenv

print('Starting WhisperWriter...')
load_dotenv()

parser = argparse.ArgumentParser(description='WhisperWriter')
parser.add_argument('--server', action='store_true',
                    help='Run as transcription server on localhost:47892 (for use on the GPU machine)')
parser.add_argument('--remote', action='store_true',
                    help='Send audio to remote transcription server at localhost:47892 (requires SSH tunnel to gratitude)')
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
    subprocess.run([sys.executable, os.path.join('src', 'main.py')], env=env)
