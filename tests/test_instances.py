import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
source = pathlib.Path(__file__).resolve().parents[1] / 'gomuks_web/rootfs'
sys.path.insert(0, str(source if source.is_dir() else pathlib.Path('/opt/addon')))
try:
    import bcrypt
except ImportError:
    raise unittest.SkipTest('Instance tests run in the add-on image with bcrypt installed')
from settings import validate
from instances import InstancePool, CapacityError, migrate_legacy, rewrite_paths

A, B, C = 'a'*32, 'b'*32, 'c'*32


class MigrationTests(unittest.TestCase):
    def test_missing_owner_never_assigns_legacy_to_visitor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root/'gomuks').mkdir()
            (root/'gomuks/keys').write_text('legacy-key-fixture')
            with self.assertRaises(ValueError):
                migrate_legacy(root, '')
            self.assertEqual((root/'gomuks/keys').read_text(), 'legacy-key-fixture')
            self.assertFalse((root/'users').exists())
            migrate_legacy(root, A)
            self.assertEqual((root/'users'/A/'gomuks/keys').read_text(), 'legacy-key-fixture')
            self.assertFalse((root/'users'/B).exists())
            migrate_legacy(root, A)  # no duplicate migration

    def test_conflicting_target_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root/'gomuks').mkdir()
            (root/'users'/A/'gomuks').mkdir(parents=True)
            with self.assertRaises(ValueError):
                migrate_legacy(root, A)
            self.assertTrue((root/'gomuks').is_dir())

    def test_absolute_log_paths_follow_moved_owner(self):
        config = {'logging': {'writers': [{'filename': '/data/gomuks/logs/test.log'}]},
                  'web': {'origin_patterns': ['ha.example.de']}}
        updated = rewrite_paths(config, '/data/gomuks', '/data/users/'+A+'/gomuks')
        self.assertEqual(updated['logging']['writers'][0]['filename'], '/data/users/'+A+'/gomuks/logs/test.log')
        self.assertEqual(updated['web'], config['web'])


class PoolTests(unittest.TestCase):
    def make_pool(self, directory, users=None):
        return InstancePool(validate(dict(public_origins=['https://ha.example.de'],
                                         allowed_user_ids=users or [], max_instances=2)),
                            pathlib.Path(directory))

    def test_untrusted_ids_and_allowlist_never_start_process(self):
        with tempfile.TemporaryDirectory() as directory:
            pool = self.make_pool(directory, [A])
            with patch('instances.subprocess.Popen') as spawn:
                for user in ('', '../data', B, A.upper(), A+','+B):
                    with self.assertRaises(PermissionError):
                        pool.get(user)
                spawn.assert_not_called()
            self.assertEqual(list((pathlib.Path(directory)/'users').iterdir()), [])
            pool.stop()

    def test_symlinked_user_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            pool = self.make_pool(directory)
            (pathlib.Path(directory)/'users'/A).symlink_to('/tmp')
            with self.assertRaises(ValueError):
                pool.get(A)
            pool.stop()


if __name__ == '__main__':
    unittest.main()
