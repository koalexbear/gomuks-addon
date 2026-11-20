"""Run inside the built image, without external network access or Matrix login."""
import http.client
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
sys.path.insert(0, '/opt/addon')
from settings import validate, nginx_config
from instances import InstancePool, auth_server, CapacityError

A, B, C = 'a'*32, 'b'*32, 'c'*32
ORIGIN = 'https://ha.example.de'
settings = validate(dict(public_origins=[ORIGIN], max_instances=2, allowed_user_ids=[A, B, C]))


def request(user=None, path='/_gomuks/test', extra=None, body=None):
    headers = {'Host': 'ha.example.de', 'Origin': ORIGIN}
    if user is not None:
        headers['X-Remote-User-Id'] = user
    headers.update(extra or {})
    connection = http.client.HTTPConnection('127.0.0.1', 8099, timeout=30)
    connection.request('POST' if body is not None else 'GET', path, headers=headers, body=body)
    response = connection.getresponse()
    result = response.status, response.getheader('Set-Cookie'), response.read()
    connection.close()
    return result


def websocket(user):
    connection = socket.create_connection(('127.0.0.1', 8099), timeout=10)
    connection.sendall((f'GET /_gomuks/websocket HTTP/1.1\r\nHost: ha.example.de\r\nOrigin: {ORIGIN}\r\n'
                        f'X-Remote-User-Id: {user}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                        'Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n').encode())
    data = b''
    while b'\r\n\r\n' not in data:
        data += connection.recv(4096)
    headers, frame = data.split(b'\r\n\r\n', 1)
    assert b'101' in headers.split(b'\r\n')[0]
    while len(frame) < 34:
        part = connection.recv(4096)
        if not part:
            break
        frame += part
    connection.close()
    assert frame[:2] == b'\x81\x20' and frame[2:34] == user.encode()


with tempfile.TemporaryDirectory() as directory:
    pool = InstancePool(settings, Path(directory), command=[sys.executable, '/tests/fake_backend.py'])
    server = auth_server(pool)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = nginx_config(settings)
    try:
        for simulate in (False, True):
            conf = Path(directory)/'nginx.conf'
            conf.write_text(config.replace('allow 172.30.32.2;', 'allow 127.0.0.1;') if simulate else config)
            subprocess.run(['nginx', '-t', '-c', str(conf)], check=True)
            proxy = subprocess.Popen(['nginx', '-c', str(conf), '-g', 'daemon off;'])
            try:
                for _ in range(50):
                    try:
                        request()
                        break
                    except ConnectionError:
                        time.sleep(.1)
                if not simulate:
                    assert request(A, extra={'X-Forwarded-For': '172.30.32.2'})[0] == 403
                    assert not pool.instances
                    continue
                for user in (None, '', A.upper(), A+','+B, 'd'*32):
                    assert request(user)[0] == 403
                assert not pool.instances
                assert request(A, extra={'Origin': 'https://evil.test'})[0] == 403
                with ThreadPoolExecutor(max_workers=3) as clients:
                    results = list(clients.map(lambda _: request(A), range(3)))
                assert all(result[2] == A.encode()+b':' for result in results)
                assert len(pool.instances) == 1
                for user in (A, B):
                    status, cookie, body = request(user)
                    assert (status, cookie, body) == (200, None, user.encode()+b':')
                    assert request(user, extra={'Cookie': 'gomuks_auth=other-user', 'Authorization': 'Basic forged'})[2] == user.encode()+b':'
                    assert request(user, path='/_gomuks/upload', body=b'attachment')[2] == user.encode()+b':attachment'
                    assert request(user, path='/_gomuks/sse')[2] == b'data: '+user.encode()+b'\n\n'
                    websocket(user)
                keepalive = http.client.HTTPConnection('127.0.0.1', 8099, timeout=10)
                for user in (A, B, A):
                    keepalive.request('GET', '/_gomuks/test', headers={
                        'Host': 'ha.example.de', 'Origin': ORIGIN, 'X-Remote-User-Id': user})
                    response = keepalive.getresponse()
                    assert response.status == 200 and response.read() == user.encode()+b':'
                keepalive.close()
                assert pool.instances[A].port != pool.instances[B].port
                assert pool.instances[A].authorization != pool.instances[B].authorization
                assert request(A, path='/_addon_auth')[0] == 404
                assert request(A, path='/element-call-embedded/index.html')[0] == 404
                assert request(C)[0] == 503
                assert not (Path(directory)/'users'/C).exists()
                # Crash/restart only A; B must keep its identity and process.
                b_pid = pool.instances[B].process.pid
                pool.instances[A].process.terminate()
                pool.instances[A].process.wait(timeout=5)
                assert request(A)[2] == A.encode()+b':'
                assert pool.instances[B].process.pid == b_pid
            finally:
                proxy.terminate()
                proxy.wait(timeout=5)
    finally:
        server.shutdown()
        server.server_close()
        pool.stop()
print('PASS: per-user HTTP/SSE/upload/WebSocket routing, cookie isolation, gates, capacity and recovery')

# Also start actual gomuks binaries: distinct roots, credentials, databases, and restart persistence.
with tempfile.TemporaryDirectory() as directory:
    pool = InstancePool(settings, Path(directory))
    try:
        a, b = pool.get(A), pool.get(B)
        assert a.port != b.port and a.authorization != b.authorization
        for user in (A, B):
            assert any((Path(directory)/'users'/user/'gomuks/data').iterdir())
        pool.stop()
        pool = InstancePool(settings, Path(directory))
        assert pool.get(A).process.poll() is None
        assert (Path(directory)/'users'/B/'gomuks/data').is_dir()
    finally:
        pool.stop()
print('PASS: real gomuks instances start with independent persistent roots and restart successfully')
