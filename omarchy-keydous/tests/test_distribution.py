# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parent.parent


def module(name):
    spec=importlib.util.spec_from_file_location('distribution_'+name,ROOT/'scripts'/(name+'.py'))
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


installer=module('install')
packager=module('package')


class DistributionTests(unittest.TestCase):
    def test_installer_preserves_settings_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            config=root/'config'
            state=root/'state'
            shell=config/'omarchy/shell.json'
            shell.parent.mkdir(parents=True)
            original=dict(version=1,idle={'lock':300},bar={'layout':{'left':[{'id':'omarchy.menu'}],'right':[]}},disabledPlugins=['eg.keydous','other'])
            shell.write_text(json.dumps(original))
            destination,backup=installer.install(ROOT,config,state,True)
            changed=json.loads(shell.read_text())
            self.assertEqual(changed['idle'],original['idle'])
            self.assertEqual(changed['bar']['layout']['left'],original['bar']['layout']['left'])
            self.assertEqual(changed['bar']['layout']['right'],[{'id':'eg.keydous'}])
            self.assertEqual(changed['disabledPlugins'],['other'])
            self.assertEqual(json.loads((backup/'shell.json').read_text()),original)
            self.assertTrue((destination/'docs/firmware.md').is_file())
            self.assertFalse((destination/'tests').exists())
            _,second_backup=installer.install(ROOT,config,state,True)
            self.assertTrue((second_backup/'plugin/Panel.qml').is_file())
            self.assertEqual(json.loads(shell.read_text()),changed)

    def test_install_without_enable_leaves_config_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            shell=root/'config/omarchy/shell.json'
            shell.parent.mkdir(parents=True)
            shell.write_text('{"version": 1, "custom": true}\n')
            before=shell.read_bytes()
            installer.install(ROOT,root/'config',root/'state',False)
            self.assertEqual(shell.read_bytes(),before)

    def test_installer_rejects_bad_config_before_installing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            shell=root/'config/omarchy/shell.json'
            shell.parent.mkdir(parents=True)
            shell.write_text('not json')
            with self.assertRaises(ValueError):
                installer.install(ROOT,root/'config',root/'state',True)
            self.assertFalse((root/'config/omarchy/plugins/eg.keydous').exists())

    def test_archive_is_reproducible_and_allowlisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            first=packager.build(ROOT,Path(temporary)/'one.zip')
            second=packager.build(ROOT,Path(temporary)/'two.zip')
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(),hashlib.sha256(second.read_bytes()).digest())
            with zipfile.ZipFile(first) as archive:
                names=archive.namelist()
                self.assertEqual(set(names),{'eg.keydous/'+name for name in packager.FILES})
                self.assertTrue(all(not name.endswith(('.exe','.bin','.dll','.dmg')) for name in names))
                self.assertNotIn('vendor-analysis',str(names))
                manifest=json.loads(archive.read('eg.keydous/manifest.json'))
                self.assertIn('eg.keydous/'+manifest['entryPoints']['barWidget'],names)


if __name__ == '__main__':
    unittest.main()
