import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

import yaml
from settings import validate, nginx_config
from instances import InstancePool, migrate_legacy, auth_server


def main():
    os.umask(0o077)
    settings = validate(json.loads(Path('/data/options.json').read_text()))
    migrate_legacy(Path('/data'), settings.legacy_owner)
    Path('/run/nginx.conf').write_text(nginx_config(settings))
    subprocess.run(['nginx', '-t', '-c', '/run/nginx.conf'], check=True)
    pool = InstancePool(settings)
    server = auth_server(pool)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    env = {key: value for key, value in os.environ.items() if key != 'SUPERVISOR_TOKEN'}
    proxy = None
    code = 0
    try:
        proxy = subprocess.Popen(['nginx', '-c', '/run/nginx.conf', '-g', 'daemon off;'], env=env)
        while not stopping.wait(.25):
            if proxy.poll() is not None or not thread.is_alive():
                code = 1
                break
    finally:
        if proxy is not None and proxy.poll() is None:
            proxy.terminate()
        server.shutdown()
        server.server_close()
        pool.stop()
        if proxy is not None:
            try:
                proxy.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proxy.kill()
                proxy.wait()
    return code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, yaml.YAMLError):
        raise SystemExit('Startup failed: check HTTPS origins and the explicit owner of existing single-user data. No data is assigned to a visitor automatically.')
