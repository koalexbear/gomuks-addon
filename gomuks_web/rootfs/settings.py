"""Validate untrusted options before interpolating nginx configuration."""
import re
from urllib.parse import urlsplit


def validate(options):
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


def nginx_config(user, origin, basic):
    # Regex matching is case sensitive; nginx literal map keys are NOT.
    return r'''
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
        add_header Permissions-Policy "microphone=(), camera=(), display-capture=()" always;
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
'''.replace('USER_ID', user).replace('ORIGIN', re.escape(origin)).replace('BASIC', basic)
