"""Test backend: echoes the selected user only after valid backend Basic auth."""
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import bcrypt
import yaml

root = Path(os.environ['GOMUKS_ROOT'])
config = yaml.safe_load((root/'config/config.yaml').read_text())['web']
port = int(config['listen_address'].rsplit(':', 1)[1])
identity = root.parent.name.encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self):
        if self.path == '/' and not self.headers.get('Authorization'):
            self.send_response(200)  # readiness only
            self.end_headers()
            return
        valid = False
        try:
            username, password = base64.b64decode(self.headers['Authorization'].split(' ', 1)[1]).decode().split(':', 1)
            valid = username == config['username'] and bcrypt.checkpw(password.encode(), config['password_hash'].encode())
        except (ValueError, TypeError, AttributeError, KeyError):
            pass
        if not valid:
            self.send_error(401)
            return
        if self.headers.get('Upgrade') == 'websocket':
            self.send_response(101)
            self.send_header('Upgrade', 'websocket')
            self.send_header('Connection', 'Upgrade')
            self.end_headers()
            self.wfile.write(bytes((0x81, len(identity)))+identity)
            self.wfile.flush()
            return
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        self.send_response(200)
        self.send_header('Set-Cookie', 'gomuks_auth=test-cookie-must-be-hidden')
        self.end_headers()
        if self.path.startswith('/_gomuks/sse'):
            self.wfile.write(b'data: '+identity+b'\n\n')
        else:
            self.wfile.write(identity+b':'+body)

    do_GET = respond
    do_POST = respond


HTTPServer(('127.0.0.1', port), Handler).serve_forever()
