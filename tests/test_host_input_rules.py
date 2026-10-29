"""Disposable filesystem/command tests, not physical input-isolation proof."""
import functools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import host_install as installer


class InputRulesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.dirs = tuple(self.root / name / 'rules.d' for name in ('etc', 'run', 'lib'))
        for directory in self.dirs:
            directory.mkdir(parents=True)
        self.target = self.dirs[0] / '85-wolf.rules'
        self.content = installer.INPUT_RULES.read_bytes()
        self.command = self.root / 'udevadm'
        self.command.touch()
        for name, value in (('UDEV_RULES_DIRS', self.dirs), ('UDEVADM', self.command)):
            patch = mock.patch.object(installer, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        # CI normally runs unprivileged; only fixture ownership uses its UID.
        self.plan = functools.partial(installer._input_rules_plan, owner_uid=os.getuid())

    def prepare(self):
        with mock.patch.object(installer, '_input_rules_plan', self.plan):
            installer._prepare_input_rules()

    def test_read_only_review_creates_nothing(self):
        target, data, exists = self.plan()
        self.assertEqual(target, self.target)
        self.assertEqual(data, self.content)
        self.assertFalse(exists)
        self.assertFalse(target.exists())

    def test_install_reload_without_trigger_and_preserve_unrelated_rules(self):
        other = self.dirs[0] / '80-keyboard.rules'
        other.write_text('# unrelated keyboard policy\n')
        with mock.patch.object(installer.subprocess, 'run', return_value=mock.Mock(returncode=0)) as run:
            self.prepare()
        self.assertEqual(self.target.read_bytes(), self.content)
        self.assertEqual(other.read_text(), '# unrelated keyboard policy\n')
        self.assertEqual(run.call_args.args[0], [str(self.command), 'control', '--reload-rules'])
        self.assertEqual(run.call_args.kwargs['timeout'], 15)
        self.assertEqual(self.target.stat().st_mode & 0o022, 0)

    def test_identical_existing_rule_is_not_rewritten(self):
        self.target.write_bytes(self.content)
        before = self.target.stat()
        with mock.patch.object(installer.subprocess, 'run', return_value=mock.Mock(returncode=0)):
            self.prepare()
        self.assertEqual(before.st_ino, self.target.stat().st_ino)
        self.assertEqual(before.st_mtime_ns, self.target.stat().st_mtime_ns)

    def test_conflicting_named_or_renamed_rules_are_preserved(self):
        for directory in self.dirs:
            for filename, data in [('85-wolf.rules', b'# custom\n'),
                                   ('99-input.rules', b'# Wolf custom input policy\n')]:
                with self.subTest(directory=directory, filename=filename):
                    path = directory / filename
                    path.write_bytes(data)
                    with self.assertRaisesRegex(installer.InstallationError, 'owner review'):
                        self.plan()
                    self.assertEqual(path.read_bytes(), data)
                    path.unlink()

    def test_symlink_mask_and_writable_directory_refused(self):
        self.target.symlink_to('/dev/null')
        with self.assertRaises(installer.InstallationError):
            self.plan()
        self.target.unlink()
        self.dirs[0].chmod(0o777)
        with self.assertRaisesRegex(installer.InstallationError, 'Untrusted'):
            self.plan()

    def test_untrusted_existing_rule_refused(self):
        self.target.write_bytes(self.content)
        self.target.chmod(0o666)
        with self.assertRaises(installer.InstallationError):
            self.plan()

    def test_modified_packaged_rule_and_missing_udevadm_refused(self):
        bad = self.root / 'bad.rules'
        bad.write_text('changed')
        with mock.patch.object(installer, 'INPUT_RULES', bad):
            with self.assertRaisesRegex(installer.InstallationError, 'integrity'):
                self.plan()
        self.command.unlink()
        with self.assertRaisesRegex(installer.InstallationError, 'udevadm'):
            self.plan()

    def test_reload_failure_retains_exact_rule_for_recovery(self):
        for failure in (mock.Mock(returncode=1), subprocess.TimeoutExpired('udevadm', 15)):
            with self.subTest(failure=failure):
                kwargs = ({'side_effect': failure} if isinstance(failure, Exception)
                          else {'return_value': failure})
                with mock.patch.object(installer.subprocess, 'run', **kwargs):
                    with self.assertRaisesRegex(installer.InstallationError, 'retained'):
                        self.prepare()
                self.assertEqual(self.target.read_bytes(), self.content)

    def test_file_appearing_after_review_is_never_overwritten(self):
        decision = self.plan()
        self.target.write_bytes(b'other owner policy')
        with mock.patch.object(installer, '_input_rules_plan', return_value=decision):
            with self.assertRaises(FileExistsError):
                installer._prepare_input_rules()
        self.assertEqual(self.target.read_bytes(), b'other owner policy')

    def test_install_aborts_before_docker_if_reload_fails(self):
        workspace = self.root / 'managed' / 'host'
        workspace.parent.mkdir(mode=0o700)
        with (mock.patch.object(installer, 'ROOT', workspace.parent),
              mock.patch.object(installer, 'WORKSPACE', workspace),
              mock.patch.object(installer, 'LOCK_PATH', self.root / 'install.lock'),
              mock.patch.object(installer.os, 'geteuid', return_value=0),
              mock.patch.object(installer, '_host_checks', return_value={'decision': 'candidate'}),
              mock.patch.object(installer, '_input_rules_plan', self.plan),
              mock.patch.object(installer.subprocess, 'run', return_value=mock.Mock(returncode=1)),
              mock.patch.object(installer, '_docker') as docker):
            # ROOT is created by the installer so the normal root-ownership
            # check needn't be relaxed for the unprivileged CI fixture.
            workspace.parent.rmdir()
            with self.assertRaisesRegex(installer.InstallationError, 'reload failed'):
                installer.install('intel', '/dev/dri/renderD128', 'sha256:' + 'a'*64, 'INSTALL-WOLF')
            docker.assert_not_called()
        state = json.loads((workspace / 'install-state.json').read_text())
        self.assertEqual(state['phase'], 'preparing_input_rules')
        self.assertFalse(state['stream_verified'])
        self.assertEqual(self.target.read_bytes(), self.content)


if __name__ == '__main__':
    unittest.main()
