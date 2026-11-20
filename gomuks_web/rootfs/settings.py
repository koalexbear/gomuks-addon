"""Validate untrusted options before interpolating nginx configuration."""
import re
import ipaddress
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True)
class DesktopSettings:
    origin: str
    authority: str
    proxy_host: str
    username: str
    password: str = field(repr=False)


def desktop_settings(options):
    value = options.get('desktop', {})
    if not isinstance(value, dict) or type(value.get('enabled', False)) is not bool:
        raise ValueError('desktop.enabled must be a boolean')
    if not value.get('enabled', False):
        return None
    origin = value.get('public_origin', '')
    if not isinstance(origin, str) or not re.fullmatch(r'https://[a-z0-9.-]+(?::[0-9]{1,5})?', origin):
        raise ValueError('desktop.public_origin must be an exact HTTPS origin')
    parsed = urlsplit(origin)
    if not parsed.hostname or (parsed.port is not None and not 1 <= parsed.port <= 65535):
        raise ValueError('invalid desktop origin port')
    host = value.get('proxy_host', '')
    if not isinstance(host, str) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,252}', host):
        raise ValueError('desktop.proxy_host must be the internal NPM hostname')
    username = value.get('username', '')
    if not isinstance(username, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,32}', username):
        raise ValueError('invalid desktop username')
    password = value.get('password', '')
    if (not isinstance(password, str) or len(password) < 20 or
            len(password.encode('utf-8')) > 72 or any(ord(c) < 32 or ord(c) == 127 for c in password)):
        raise ValueError('desktop password must be at least 20 characters and at most 72 UTF-8 bytes')
    return DesktopSettings(origin, parsed.netloc, host, username, password)


def private_proxy_ip(value):
    address = ipaddress.IPv4Address(value)
    networks = ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')
    if not any(address in ipaddress.IPv4Network(net) for net in networks):
        raise ValueError('NPM must resolve to a private IPv4 address')
    return str(address)


def validate(options):
    if type(options.get('enable_calls', False)) is not bool:
        raise ValueError('enable_calls must be a boolean')
    desktop_settings(options)
    user = options.get('allowed_user_id', '')
    if not isinstance(user, str) or not re.fullmatch(r'[0-9a-f]{32}', user):
        raise ValueError('allowed_user_id must be the exact 32-character lowercase HA user ID')
    origin = options.get('public_origin', '')
    if not isinstance(origin, str) or not re.fullmatch(r'https://[a-z0-9.-]+(?::[0-9]{1,5})?', origin):
        raise ValueError('public_origin must be an exact HTTPS origin without a path or trailing slash')
    parsed = urlsplit(origin)
    if not parsed.hostname or (parsed.port is not None and not 1 <= parsed.port <= 65535):
        raise ValueError('invalid public_origin port')
    return user, origin, parsed.netloc


def nginx_config(user, origin, basic, enable_calls=False, desktop=None, desktop_proxy_ip=None):
    if type(enable_calls) is not bool:
        raise ValueError("enable_calls must be a boolean")
    policy = ("microphone=(self), camera=(self), display-capture=()" if enable_calls
              else "microphone=(), camera=(), display-capture=()")
    # Regex matching is case sensitive; nginx literal map keys are NOT.
    config = r'''
worker_processes 1;
pid /run/nginx/nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 256; }
http {
    # Log only 403 decisions, never raw request/header values.
    geo $peer_ok { default 0; 172.30.32.2/32 1; }
    map $http_x_remote_user_id $id_present { default 1; "" 0; }
    map $status $log_denial { default 0; 403 1; }
    log_format ingress_gate 'ingress_gate status=$status peer_ok=$peer_ok '
        'id_present=$id_present user_ok=$user_ok origin_ok=$origin_ok '
        'upstream_status=$upstream_status';
    access_log /dev/stderr ingress_gate if=$log_denial;
    map $http_x_remote_user_id $user_ok {
        default 0;
        ~^USER_ID$ 1;
    }
    map $http_origin $origin_ok {
        default 0;
        "" 1;
        ~^ORIGIN$ 1;
    }
    map $http_upgrade $connection_upgrade { default upgrade; "" close; }
    server {
        listen 8099;
        server_name _;
        allow 172.30.32.2;
        deny all;
        if ($user_ok = 0) { return 403; }
        if ($origin_ok = 0) { return 403; }
        client_max_body_size 50m;
        add_header Cache-Control "no-store" always;
        add_header Permissions-Policy "CALL_POLICY" always;
        location / {
            proxy_pass http://127.0.0.1:29325;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Authorization "Basic BASIC";
            # Backend credentials/cookies never leave this container.
            proxy_set_header Cookie "";
            proxy_hide_header Set-Cookie;
            proxy_hide_header Cache-Control;
            proxy_hide_header WWW-Authenticate;
            proxy_set_header X-Remote-User-Id "";
            proxy_set_header X-Remote-User-Name "";
            proxy_set_header X-Remote-User-Display-Name "";
            proxy_set_header X-Forwarded-For "";
            proxy_buffering off;
            proxy_request_buffering off;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }
    }
}
'''.replace('USER_ID', user).replace('ORIGIN', re.escape(origin)).replace('BASIC', basic).replace('CALL_POLICY', policy)

    if desktop is not None:
        peer = private_proxy_ip(desktop_proxy_ip)
        # No injected credentials on this route: upstream gomuks authenticates
        # native clients at /_gomuks/auth and checks API cookies thereafter.
        server = r"""
    map $http_origin $desktop_origin_ok {
        default 0;
        "" 1;
        ~^DESKTOP_ORIGIN$ 1;
    }
    map $http_host $desktop_host_ok {
        default 0;
        ~^DESKTOP_AUTHORITY$ 1;
    }
    server {
        listen 8098;
        server_name _;
        access_log off;
        allow DESKTOP_PEER;
        deny all;
        if ($desktop_host_ok = 0) { return 403; }
        if ($desktop_origin_ok = 0) { return 403; }
        if ($http_x_forwarded_proto != "https") { return 403; }
        client_max_body_size 50m;
        add_header Cache-Control "no-store" always;
        add_header Permissions-Policy "DESKTOP_POLICY" always;
        location / {
            proxy_pass http://127.0.0.1:29325;
            proxy_http_version 1.1;
            proxy_set_header Host $http_host;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Authorization $http_authorization;
            proxy_set_header Cookie $http_cookie;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header X-Forwarded-For "";
            proxy_set_header X-Remote-User-Id "";
            proxy_set_header X-Remote-User-Name "";
            proxy_set_header X-Remote-User-Display-Name "";
            proxy_hide_header Cache-Control;
            proxy_buffering off;
            proxy_request_buffering off;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }
    }
""".replace('DESKTOP_ORIGIN', re.escape(desktop.origin)).replace(
            'DESKTOP_AUTHORITY', re.escape(desktop.authority)).replace(
            'DESKTOP_PEER', peer).replace('DESKTOP_POLICY', policy)
        config = config.rsplit('}', 1)[0] + server + '}\n'
    return config
