import base64
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import time

import bcrypt
import yaml
from settings import validate, nginx_config


def main():
    os.umask(0o077)
    user, origin, authority = validate(json.loads(Path('/data/options.json').read_text()))
    root = Path('/data/gomuks')
    for name in ('config', 'data', 'cache', 'logs'):
        folder = root / name
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        folder.chmod(0o700)
    config_path = root / 'config/config.yaml'
    config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    config = config or {}
    # Keep token keys, encryption settings and future upstream fields across restarts.
    password = secrets.token_urlsafe(32)
    config.setdefault('web', {}).update({
        'listen_address': '127.0.0.1:29325',
        'username': 'ingress',
        'password_hash': bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode(),
        'origin_patterns': [authority],
        'insecure_cookies': False,
        'debug_endpoints': False,
        'disable_auth_because_i_want_my_account_to_be_hacked': False,
    })
    temp = config_path.with_suffix('.tmp')
    temp.write_text(yaml.safe_dump(config))
    temp.chmod(0o600)
    temp.replace(config_path)
    basic = base64.b64encode(f'ingress:{password}'.encode()).decode()
    Path('/run/nginx.conf').write_text(nginx_config(user, origin, basic))
    subprocess.run(['nginx', '-t', '-c', '/run/nginx.conf'], check=True)
    # Do not pass Supervisor credentials to child processes.
    env = {k: v for k, v in os.environ.items() if k != 'SUPERVISOR_TOKEN'}
    env['GOMUKS_ROOT'] = str(root)
    children = []
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    code = 0
    try:
        children.append(subprocess.Popen(['/usr/bin/gomuks'], env=env))
        children.append(subprocess.Popen(['nginx', '-c', '/run/nginx.conf', '-g', 'daemon off;'], env=env))
        while not stopping:
            if any(child.poll() is not None for child in children):
                code = 1
                break
            time.sleep(0.25)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 45
        for child in children:
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    return code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, yaml.YAMLError):
        # Avoid dumping options, tokens or credentials in tracebacks.
        raise SystemExit('Startup configuration invalid or inaccessible; check user ID and HTTPS origin.')
