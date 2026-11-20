"""Real gomuks + nginx handshake, without a Matrix account. Run in built image."""
import base64
import http.client
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import bcrypt
import yaml
sys.path.insert(0, '/opt/addon')
from settings import desktop_settings, nginx_config

ORIGIN = 'https://gomuks.example.de'
PASSWORD = secrets.token_urlsafe(24)
USERNAME = 'desktop'
BASIC = 'Basic ' + base64.b64encode(f'{USERNAME}:{PASSWORD}'.encode()).decode()


def request(path, headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', 8098, timeout=5)
    merged = {'Host': 'gomuks.example.de', 'X-Forwarded-Proto': 'https', 'Origin': ORIGIN}
    merged.update(headers or {})
    connection.request('GET' if path != '/_gomuks/auth' else 'POST', path, headers=merged)
    response = connection.getresponse()
    status, cookie = response.status, response.getheader('Set-Cookie')
    if status != 101:
        response.read()
    connection.close()
    return status, cookie


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'config').mkdir()
    config = {'web': {'listen_address': '127.0.0.1:29325', 'username': USERNAME,
                     'password_hash': bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
                     'origin_patterns': ['gomuks.example.de'], 'insecure_cookies': False,
                     'disable_auth_because_i_want_my_account_to_be_hacked': False}}
    (root / 'config/config.yaml').write_text(yaml.safe_dump(config))
    env = {k: v for k, v in os.environ.items() if k != 'SUPERVISOR_TOKEN'}
    env['GOMUKS_ROOT'] = directory
    backend = subprocess.Popen(['/usr/bin/gomuks'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proxies = []
    try:
        for _ in range(100):
            try:
                c = http.client.HTTPConnection('127.0.0.1', 29325, timeout=1)
                c.request('GET', '/')
                c.getresponse().read()
                c.close()
                break
            except OSError:
                if backend.poll() is not None:
                    raise AssertionError('gomuks exited')
                time.sleep(.1)
        else:
            raise AssertionError('gomuks startup timeout')
        desktop = desktop_settings({'desktop': dict(enabled=True, public_origin=ORIGIN,
                                    proxy_host='npm-addon', username=USERNAME, password=PASSWORD)})
        config = nginx_config('a'*32, 'https://ha.example.de', 'INTERNAL',
                              desktop=desktop, desktop_proxy_ip='172.30.33.5')
        # First prove production peer check; only then simulate the NPM peer in test.
        for simulate in (False, True):
            generated = config.replace('allow 172.30.33.5;', 'allow 127.0.0.1;') if simulate else config
            conf = root / 'nginx.conf'
            conf.write_text(generated)
            subprocess.run(['nginx', '-t', '-c', str(conf)], check=True)
            proxy = subprocess.Popen(['nginx', '-c', str(conf), '-g', 'daemon off;'])
            proxies.append(proxy)
            try:
                for _ in range(50):
                    try:
                        request('/')
                        break
                    except OSError:
                        if proxy.poll() is not None:
                            raise AssertionError('nginx exited')
                        time.sleep(.1)
                if not simulate:
                    assert request('/_gomuks/auth', {'Authorization': BASIC,
                                                    'X-Forwarded-For': '172.30.33.5'})[0] == 403
                else:
                    assert request('/')[0] == 200, 'native client must load frontend without challenge'
                    assert request('/_gomuks/auth')[0] == 401
                    assert request('/_gomuks/auth', {'Authorization': 'Basic eDp5'})[0] == 401
                    assert request('/_gomuks/websocket', {'X-Remote-User-Id': 'a'*32})[0] == 401
                    status, cookie = request('/_gomuks/auth', {'Authorization': BASIC})
                    assert status in (200, 201) and cookie
                    assert 'Secure' in cookie and 'HttpOnly' in cookie
                    session = cookie.split(';', 1)[0]
                    ws = {'Cookie': session, 'Connection': 'Upgrade', 'Upgrade': 'websocket',
                          'Sec-WebSocket-Version': '13', 'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ=='}
                    assert request('/_gomuks/websocket', ws)[0] == 101, 'cookie-authenticated websocket'
                    assert request('/_gomuks/auth', {'Authorization': BASIC, 'Origin': 'https://evil.test'})[0] == 403
                    assert request('/_gomuks/auth', {'Authorization': BASIC, 'Host': 'evil.test'})[0] == 403
                    assert request('/_gomuks/auth', {'Authorization': BASIC, 'X-Forwarded-Proto': 'http'})[0] == 403
            finally:
                proxy.terminate()
                proxy.wait(timeout=5)
    finally:
        backend.terminate()
        backend.wait(timeout=15)
print('PASS: desktop frontend, credentials, secure cookie, WebSocket, peer/origin/host/TLS gates')
