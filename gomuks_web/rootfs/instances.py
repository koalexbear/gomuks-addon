"""One backend process and private persistent root per authenticated HA user."""
import base64
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
from dataclasses import dataclass, field

import bcrypt
import yaml
from settings import valid_user_id


def private_directory(path):
    if path.is_symlink():
        raise ValueError('Private data directory must not be a symlink')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def rewrite_paths(value, source, target):
    if isinstance(value, dict):
        return {key: rewrite_paths(item, source, target) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_paths(item, source, target) for item in value]
    if isinstance(value, str) and (value == source or value.startswith(source + '/')):
        return target + value[len(source):]
    return value


def migrate_legacy(data, owner):
    """Rename only with an explicit owner; never assign data to the first visitor."""
    legacy = data / 'gomuks'
    if legacy.is_symlink():
        raise ValueError('Legacy data root must not be a symlink')
    if not legacy.exists():
        return
    if not legacy.is_dir():
        raise ValueError('Legacy data root must be a directory')
    if not valid_user_id(owner):
        raise ValueError('Existing data requires legacy_owner_id (or the previous allowed_user_id)')
    private_directory(data / 'users')
    private_directory(data / 'users' / owner)
    target = data / 'users' / owner / 'gomuks'
    if target.exists() or target.is_symlink():
        raise ValueError('Both legacy and owner data exist; restore/resolve offline before starting')
    os.replace(legacy, target)
    # Absolute paths in the moved config are rewritten on the owner's next start.


@dataclass
class Instance:
    port: int
    process: subprocess.Popen
    authorization: str = field(repr=False)


class CapacityError(Exception):
    pass


class InstancePool:
    def __init__(self, settings, data=Path('/data'), command=None, ready_timeout=20):
        self.settings = settings
        self.data = Path(data)
        self.command = command or ['/usr/bin/gomuks']
        self.ready_timeout = ready_timeout
        self.instances = {}
        self.lock = threading.RLock()
        self.closed = False
        private_directory(self.data / 'users')

    def permitted(self, user):
        return valid_user_id(user) and (not self.settings.allowed_users or user in self.settings.allowed_users)

    def get(self, user):
        if not self.permitted(user):
            raise PermissionError('Unknown or disallowed HA user')
        with self.lock:
            if self.closed:
                raise CapacityError('Instance manager is stopping')
            for key, instance in list(self.instances.items()):
                if instance.process.poll() is not None:
                    del self.instances[key]
            if user in self.instances:
                return self.instances[user]
            if len(self.instances) >= self.settings.max_instances:
                raise CapacityError('Instance limit reached')
            used = {instance.port for instance in self.instances.values()}
            port = next(port for port in range(29325, 29325 + self.settings.max_instances) if port not in used)
            private_directory(self.data / 'users' / user)
            root = self.data / 'users' / user / 'gomuks'
            private_directory(root)
            for name in ('config', 'data', 'cache', 'logs'):
                private_directory(root / name)
            path = root / 'config/config.yaml'
            if path.is_symlink():
                raise ValueError('Config must not be a symlink')
            config = (yaml.safe_load(path.read_text()) if path.exists() else {}) or {}
            if not isinstance(config, dict) or not isinstance(config.get('web', {}), dict):
                raise ValueError('Invalid backend config')
            config = rewrite_paths(config, str(self.data / 'gomuks'), str(root))
            password = secrets.token_urlsafe(32)
            config.setdefault('web', {}).update({
                'listen_address': f'127.0.0.1:{port}',
                'username': 'ingress',
                'password_hash': bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode(),
                'token_key': secrets.token_urlsafe(64),
                'origin_patterns': list(self.settings.authorities),
                'insecure_cookies': False,
                'debug_endpoints': False,
                'disable_auth_because_i_want_my_account_to_be_hacked': False,
            })
            temp = path.with_suffix('.tmp')
            if temp.is_symlink():
                raise ValueError('Temporary config must not be a symlink')
            temp.write_text(yaml.safe_dump(config))
            temp.chmod(0o600)
            temp.replace(path)
            env = {key: value for key, value in os.environ.items()
                   if key != 'SUPERVISOR_TOKEN' and not key.startswith('GOMUKS_')}
            env['GOMUKS_ROOT'] = str(root)
            # Isolate all directories, including logs saved by upstream in config.
            process = subprocess.Popen(self.command, env=env)
            authorization = 'Basic ' + base64.b64encode(f'ingress:{password}'.encode()).decode()
            instance = Instance(port, process, authorization)
            try:
                deadline = time.monotonic() + self.ready_timeout
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError('Backend exited during startup')
                    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=.5)
                    try:
                        connection.request('GET', '/')
                        response = connection.getresponse()
                        response.read()
                        if response.status == 200:
                            self.instances[user] = instance
                            return instance
                    except OSError:
                        pass
                    finally:
                        connection.close()
                    time.sleep(.1)
                raise RuntimeError('Backend startup timed out')
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                raise

    def stop(self):
        with self.lock:
            self.closed = True
            children = [instance.process for instance in self.instances.values()]
            for child in children:
                if child.poll() is None:
                    child.terminate()
            deadline = time.monotonic() + 40
            for child in children:
                try:
                    child.wait(timeout=max(.1, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            self.instances.clear()


def auth_server(pool):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            values = self.headers.get_all('X-Remote-User-Id', [])
            if self.path != '/auth' or len(values) != 1 or not pool.permitted(values[0]):
                self.send_error(403)
                return
            try:
                instance = pool.get(values[0])
            except (CapacityError, OSError, ValueError, RuntimeError, yaml.YAMLError):
                # No IDs, paths, passwords or config dumps in response/log output.
                print('A per-user backend is unavailable or the instance limit was reached.', flush=True)
                self.send_error(503)
                return
            self.send_response(204)
            self.send_header('X-Backend-Port', str(instance.port))
            self.send_header('X-Backend-Authorization', instance.authorization)
            self.end_headers()

    server = ThreadingHTTPServer(('127.0.0.1', 29324), Handler)
    server.daemon_threads = True
    return server
