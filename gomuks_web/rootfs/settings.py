"""Ingress configuration. Only Supervisor-provided HA IDs select a backend."""
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

USER_ID = re.compile(r'[0-9a-f]{32}')


@dataclass(frozen=True)
class Settings:
    origins: tuple[str, ...]
    authorities: tuple[str, ...]
    allowed_users: frozenset[str]
    max_instances: int
    legacy_owner: str


def valid_user_id(value):
    return isinstance(value, str) and USER_ID.fullmatch(value) is not None


def validate(options):
    origins = options.get('public_origins', [])
    if not origins and options.get('public_origin'):
        origins = [options['public_origin']]
    if not isinstance(origins, list) or not 1 <= len(origins) <= 16:
        raise ValueError('Configure at least one HTTPS Home Assistant origin')
    authorities = []
    for origin in origins:
        if not isinstance(origin, str) or not re.fullmatch(r'https://[a-z0-9.-]+(?::[0-9]{1,5})?', origin):
            raise ValueError('Origins must be exact HTTPS addresses without a path or trailing slash')
        parsed = urlsplit(origin)
        if not parsed.hostname or (parsed.port is not None and not 1 <= parsed.port <= 65535):
            raise ValueError('Invalid HTTPS origin')
        authorities.append(parsed.netloc)
    users = options.get('allowed_user_ids', [])
    if not isinstance(users, list) or any(not valid_user_id(user) for user in users):
        raise ValueError('allowed_user_ids must contain exact HA user IDs')
    maximum = options.get('max_instances', 4)
    if type(maximum) is not int or not 1 <= maximum <= 16:
        raise ValueError('max_instances must be between 1 and 16')
    owner = options.get('legacy_owner_id', '') or options.get('allowed_user_id', '')
    if owner and not valid_user_id(owner):
        raise ValueError('Invalid owner ID for migration')
    return Settings(tuple(dict.fromkeys(origins)), tuple(dict.fromkeys(authorities)),
                    frozenset(users), maximum, owner)


def nginx_config(settings):
    origin_rules = '\n'.join(f'        ~^{re.escape(origin)}$ 1;' for origin in settings.origins)
    return r'''
worker_processes 1;
pid /run/nginx/nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 512; }
http {
    access_log off;
    map $http_x_remote_user_id $user_ok {
        default 0;
        "~^[0-9a-f]{32}$" 1;
    }
    map $http_origin $origin_ok {
        default 0;
        "" 1;
ORIGIN_RULES
    }
    map $http_upgrade $connection_upgrade { default upgrade; "" close; }
    map $status $log_denial { default 0; 403 1; 503 1; }
    log_format ingress_gate 'ingress_gate status=$status user_ok=$user_ok origin_ok=$origin_ok';
    access_log /dev/stderr ingress_gate if=$log_denial;
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
        # Block the bundled call app; this add-on supports chat only.
        location ^~ /element-call-embedded/ { return 404; }
        location = /_addon_auth {
            internal;
            proxy_pass http://127.0.0.1:29324/auth;
            proxy_pass_request_body off;
            proxy_set_header Content-Length "";
            proxy_set_header X-Remote-User-Id $http_x_remote_user_id;
            proxy_set_header Authorization "";
            proxy_set_header Cookie "";
        }
        location = /_addon_unavailable {
            internal;
            default_type text/plain;
            return 503 "Your chat backend is unavailable or the instance limit was reached. Contact the add-on administrator.\n";
        }
        location / {
            auth_request /_addon_auth;
            auth_request_set $backend_port $upstream_http_x_backend_port;
            auth_request_set $backend_auth $upstream_http_x_backend_authorization;
            error_page 500 502 504 =503 /_addon_unavailable;
            proxy_pass http://127.0.0.1:$backend_port;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Authorization $backend_auth;
            proxy_set_header Cookie "";
            proxy_hide_header Set-Cookie;
            proxy_hide_header WWW-Authenticate;
            proxy_hide_header Cache-Control;
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
'''.replace('ORIGIN_RULES', origin_rules)
