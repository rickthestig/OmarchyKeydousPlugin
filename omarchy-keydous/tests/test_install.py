# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

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

    def test_install_without_enable_leaves_shell_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/'config'
            installer.install(ROOT, config, Path(folder)/'state')
            self.assertFalse((config/'omarchy/shell.json').exists())
