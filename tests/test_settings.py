import pathlib
import re
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'gomuks_web/rootfs'))
from settings import validate, nginx_config, desktop_settings, private_proxy_ip

USER = 'a123456789abcdef0123456789abcdef'
ORIGIN = 'https://ha.example.de:8123'


class SettingsTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(dict(allowed_user_id=USER, public_origin=ORIGIN)),
                         (USER, ORIGIN, 'ha.example.de:8123'))

    def test_fail_closed_options(self):
        for value in ['', USER.upper(), USER + ';', USER + '\n', 'admin']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(dict(allowed_user_id=value, public_origin=ORIGIN))
        for value in ['', '*', 'http://ha.example.de', ORIGIN + '/', ORIGIN + ';',
                      'https://ha.example.de:99999', 'https://ha.example.de\ninclude /tmp/x;']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(dict(allowed_user_id=USER, public_origin=value))

    def test_calls_default_denied_and_explicit_opt_in(self):
        blocked = nginx_config(USER, ORIGIN, 'abc123')
        enabled = nginx_config(USER, ORIGIN, 'abc123', enable_calls=True)
        self.assertIn('microphone=(), camera=(), display-capture=()', blocked)
        self.assertIn('microphone=(self), camera=(self), display-capture=()', enabled)
        # Opt-in changes only this policy, never the authentication boundary.
        self.assertEqual(blocked.replace('microphone=(), camera=()',
                                         'microphone=(self), camera=(self)'), enabled)

    def test_calls_requires_boolean(self):
        for value in ('false', 'true', '', None, 0, 1, []):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate(dict(allowed_user_id=USER, public_origin=ORIGIN, enable_calls=value))
                with self.assertRaises(ValueError):
                    nginx_config(USER, ORIGIN, 'abc123', enable_calls=value)

    def desktop_options(self, **changes):
        value = dict(enabled=True, public_origin='https://gomuks.example.de',
                     proxy_host='npm-addon', username='desktop', password='x' * 24)
        value.update(changes)
        return {'desktop': value}

    def test_desktop_opt_in_and_auth_separation(self):
        self.assertIsNone(desktop_settings({}))
        disabled = nginx_config(USER, ORIGIN, 'INTERNAL')
        self.assertNotIn('listen 8098', disabled)
        desktop = desktop_settings(self.desktop_options())
        config = nginx_config(USER, ORIGIN, 'INTERNAL', desktop=desktop, desktop_proxy_ip='172.30.33.5')
        ingress, separate = config.split('listen 8098;', 1)
        self.assertIn('Basic INTERNAL', ingress)
        self.assertNotIn('INTERNAL', separate)
        self.assertIn('allow 172.30.33.5;', separate)
        self.assertIn('deny all;', separate)
        self.assertIn('Authorization $http_authorization', separate)
        self.assertIn('Cookie $http_cookie', separate)
        self.assertNotIn('proxy_hide_header Set-Cookie', separate)
        self.assertNotIn('proxy_hide_header WWW-Authenticate', separate)
        self.assertIn('if ($http_x_forwarded_proto != "https")', separate)
        self.assertIn('if ($desktop_host_ok = 0)', separate)
        self.assertNotIn(desktop.password, config)
        self.assertNotIn(desktop.password, repr(desktop))

    def test_desktop_validates_secrets_and_injection(self):
        for key, value in (('enabled', 'false'), ('username', 'x:y'),
                           ('password', 'short'), ('password', 'x'*73),
                           ('password', 'x'*24+'\n'), ('public_origin', 'https://evil.test;'),
                           ('public_origin', 'http://gomuks.test'),
                           ('proxy_host', 'npm; include /tmp/x;')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                desktop_settings(self.desktop_options(**{key: value}))
        for value in ('0.0.0.0', '127.0.0.1', '8.8.8.8', '::1', '172.30.33.5;'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                private_proxy_ip(value)
        self.assertEqual(private_proxy_ip('172.30.33.5'), '172.30.33.5')

    def test_diagnostics_do_not_log_secrets(self):
        config = nginx_config(USER, ORIGIN, 'abc123')
        log = config.split("log_format ingress_gate ", 1)[1].split(';', 1)[0]
        for secret in ('$request', '$http_authorization', '$http_cookie', '$http_origin',
                       '$http_x_remote_user_id', USER, 'abc123'):
            self.assertNotIn(secret, log)
        self.assertIn('403 1;', config)
        self.assertIn('if=$log_denial', config)

    def test_security_and_exact_case(self):
        config = nginx_config(USER, ORIGIN, 'abc123')
        self.assertIn('allow 172.30.32.2;\n        deny all;', config)
        self.assertIn('~^' + USER + '$ 1;', config)
        self.assertIn('~^' + re.escape(ORIGIN) + '$ 1;', config)
        self.assertIn('proxy_pass http://127.0.0.1:29325;', config)
        self.assertNotIn('real_ip_header', config)
        self.assertIn('proxy_set_header Cookie "";', config)


if __name__ == '__main__':
    unittest.main()
