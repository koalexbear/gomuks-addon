import pathlib
import re
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'gomuks_web/rootfs'))
from settings import validate, nginx_config

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
