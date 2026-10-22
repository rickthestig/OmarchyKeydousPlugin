# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('installer', ROOT/'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_fresh_install_and_repeat_preserve_settings_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/'config'
            state = Path(folder)/'state'
            destination, _ = installer.install(ROOT, config, state, enable=True)
            shell = config/'omarchy/shell.json'
            settings = json.loads(shell.read_text())
            settings['custom'] = {'keep': True}
            shell.write_text(json.dumps(settings))
            (destination/'old-marker').write_text('old plugin')
            _, backup = installer.install(ROOT, config, state, enable=True)
            result = json.loads(shell.read_text())
            self.assertEqual(result['custom'], {'keep': True})
            self.assertEqual(result['bar']['layout']['right'], [{'id':'eg.keydous'}])
            self.assertTrue((backup/'plugin/old-marker').is_file())
            self.assertEqual(json.loads((backup/'shell.json').read_text()), settings)
            self.assertTrue((destination/'docs/firmware.md').is_file())

    def test_staging_is_never_inside_watched_plugins(self):
        with tempfile.TemporaryDirectory() as folder:
            config, state = Path(folder)/'config', Path(folder)/'state'
            real_publish = installer.publish
            def check(staging, destination):
                self.assertNotIn(config/'omarchy/plugins', staging.parents)
                self.assertTrue((staging/'KeyboardMap.qml').is_file())
                self.assertTrue((staging/'manifest.json').is_file())
                real_publish(staging, destination)
            with patch.object(installer, 'publish', side_effect=check) as publish:
                installer.install(ROOT, config, state)
                installer.install(ROOT, config, state)
            self.assertEqual(publish.call_count, 2)

    def test_failed_publish_keeps_installed_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            config, state = Path(folder)/'config', Path(folder)/'state'
            destination, _ = installer.install(ROOT, config, state)
            marker = destination/'installed-marker'
            marker.write_text('preserve')
            with patch.object(installer, 'publish', side_effect=OSError('Simulated failure')):
                with self.assertRaises(OSError):
                    installer.install(ROOT, config, state)
            self.assertEqual(marker.read_text(), 'preserve')
            self.assertTrue((destination/'Panel.qml').is_file())
            self.assertEqual(list(config.glob('.keydous-install-*')), [])

    def test_repeat_enable_does_not_rewrite_shell_config(self):
        with tempfile.TemporaryDirectory() as folder:
            config, state = Path(folder)/'config', Path(folder)/'state'
            installer.install(ROOT, config, state, enable=True)
            shell = config/'omarchy/shell.json'
            before = shell.stat().st_mtime_ns
            installer.install(ROOT, config, state, enable=True)
            self.assertEqual(shell.stat().st_mtime_ns, before)

    def test_install_without_enable_leaves_shell_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/'config'
            installer.install(ROOT, config, Path(folder)/'state')
            self.assertFalse((config/'omarchy/shell.json').exists())
