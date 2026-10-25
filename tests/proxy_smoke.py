"""Run inside the built image. No Matrix account or secrets required."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pathlib
import subprocess
import sys
import threading
import time
sys.path.insert(0, '/opt/addon')
from settings import nginx_config

USER = 'a123456789abcdef0123456789abcdef'
ORIGIN = 'https://ha.example.de'


class Backend(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        assert self.headers.get('Authorization') == 'Basic dGVzdA=='
        assert not self.headers.get('Cookie')
        assert not self.headers.get('X-Remote-User-Id')
        if self.headers.get('Upgrade') == 'websocket':
            self.send_response(101)
            self.send_header('Upgrade', 'websocket')
            self.send_header('Connection', 'Upgrade')
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header('Set-Cookie', 'gomuks_auth=private')
            self.end_headers()
            self.wfile.write(self.path.encode())


backend = ThreadingHTTPServer(('127.0.0.1', 29325), Backend)
threading.Thread(target=backend.serve_forever, daemon=True).start()


def request(headers=None, path='/'):
    conn = http.client.HTTPConnection('127.0.0.1', 8099, timeout=3)
    conn.request('GET', path, headers=headers or {})
    response = conn.getresponse()
    status, cookies = response.status, response.getheader('Set-Cookie')
    body = response.read() if status != 101 else b''
    conn.close()
    return status, cookies, body


base = nginx_config(USER, ORIGIN, 'dGVzdA==')
for simulated in (False, True):
    config = base.replace('allow 172.30.32.2;', 'allow 127.0.0.1;') if simulated else base
    pathlib.Path('/run/proxy-test.conf').write_text(config)
    subprocess.run(['nginx', '-t', '-c', '/run/proxy-test.conf'], check=True)
    proxy = subprocess.Popen(['nginx', '-c', '/run/proxy-test.conf', '-g', 'daemon off;'])
    try:
        for _ in range(50):
            try:
                request()
                break
            except ConnectionError:
                time.sleep(.1)
        headers = {'X-Remote-User-Id': USER, 'Origin': ORIGIN}
        if not simulated:
            assert request(headers)[0] == 403, 'Production peer gate must reject localhost'
            headers['X-Forwarded-For'] = '172.30.32.2'
            assert request(headers)[0] == 403, 'Forwarded address must not bypass peer gate'
        else:
            for bad in ({}, {'X-Remote-User-Id': USER.upper()},
                        {'X-Remote-User-Id': USER + ', ' + USER},
                        dict(headers, Origin='https://evil.example')):
                assert request(bad)[0] == 403
            status, cookie, body = request(dict(headers, Cookie='gomuks_auth=stale'), '/_gomuks/media/test?id=123')
            assert (status, cookie, body) == (200, None, b'/_gomuks/media/test?id=123')
            assert request(dict(headers, Upgrade='websocket', Connection='Upgrade'), '/_gomuks/websocket')[0] == 101
    finally:
        proxy.terminate()
        proxy.wait(timeout=5)
backend.shutdown()
print('PASS: peer gate, spoof rejection, exact ID, origin, cookie isolation, paths, upgrade forwarding')
