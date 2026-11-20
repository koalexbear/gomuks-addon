import pathlib
import sys
import unittest
source = pathlib.Path(__file__).resolve().parents[1] / 'gomuks_web/rootfs'
sys.path.insert(0, str(source if source.is_dir() else pathlib.Path('/opt/addon')))
from settings import validate, nginx_config, valid_user_id

USER = 'a123456789abcdef0123456789abcdef'
ORIGIN = 'https://ha.example.de:8123'


class SettingsTests(unittest.TestCase):
    def options(self, **changes):
        value = dict(public_origins=[ORIGIN], allowed_user_ids=[], max_instances=4)
        value.update(changes)
        return value

    def test_user_ids_are_exact(self):
        self.assertTrue(valid_user_id(USER))
        for user in ('', USER.upper(), USER+'/', '../'+USER, USER+', '+USER, None):
            self.assertFalse(valid_user_id(user))

    def test_multiple_origins(self):
        settings = validate(self.options(public_origins=[ORIGIN, 'https://ha.lan.example.de']))
        self.assertEqual(settings.authorities, ('ha.example.de:8123', 'ha.lan.example.de'))
        self.assertFalse(settings.allowed_users)

    def test_invalid_options(self):
        for key, values in (
            ('public_origins', [[], '*', ['http://ha.test'], [ORIGIN+'/'], [ORIGIN+';'], ['https://ha.test:99999']]),
            ('allowed_user_ids', ['*', [USER.upper()], ['../x']]),
            ('max_instances', [0, 17, True, '4']),
            ('legacy_owner_id', ['admin', USER.upper()]),
        ):
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate(self.options(**{key: value}))

    def test_legacy_owner_and_origin_compatibility(self):
        settings = validate(dict(public_origin=ORIGIN, allowed_user_id=USER))
        self.assertEqual(settings.origins, (ORIGIN,))
        self.assertEqual(settings.legacy_owner, USER)
        self.assertFalse(settings.allowed_users)
        restricted = validate(self.options(allowed_user_ids=[USER]))
        self.assertEqual(restricted.allowed_users, {USER})

    def test_proxy_never_exposes_credentials_or_desktop(self):
        config = nginx_config(validate(self.options()))
        self.assertIn('allow 172.30.32.2;', config)
        self.assertIn('deny all;', config)
        self.assertIn('internal;\n            proxy_pass http://127.0.0.1:29324/auth;', config)
        self.assertIn('auth_request /_addon_auth;', config)
        self.assertIn('proxy_set_header Cookie "";', config)
        self.assertNotIn('listen 8098', config)
        self.assertNotIn('real_ip_header', config)
        self.assertIn('microphone=(), camera=(), display-capture=()', config)
        self.assertIn('location ^~ /element-call-embedded/ { return 404; }', config)
        log = config.split('log_format ingress_gate ', 1)[1].split(';', 1)[0]
        for forbidden in ('$request', '$http_cookie', '$http_x_remote_user_id', '$backend_auth'):
            self.assertNotIn(forbidden, log)


if __name__ == '__main__':
    unittest.main()
