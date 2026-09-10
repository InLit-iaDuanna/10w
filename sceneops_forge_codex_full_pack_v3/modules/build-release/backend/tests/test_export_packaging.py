import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from build_release.export_packaging import LocalExportAdapter, ExportBlocked, ExportCancelled, ExportBuildError
from build_release.export_templates import ELECTRON_MAIN, VITE_CONFIG, desktop_package


class PackagingTests(unittest.TestCase):
    def test_desktop_recipe_and_fixed_commands(self):
        with tempfile.TemporaryDirectory(prefix='导出 空格 ') as temporary:
            root = Path(temporary)
            web = root / 'web'
            web.mkdir()
            (web / 'index.html').write_text('<h1>游戏</h1>')
            commands = []
            adapter = LocalExportAdapter()
            def run(args, cwd, emit, cancel, stage):
                commands.append(args)
                if stage == 'desktop-package':
                    (cwd / 'artifacts').mkdir()
                    (cwd / 'artifacts/Game-win-x64.zip').write_bytes(b'fixture')
            with patch.object(adapter, '_run', side_effect=run):
                artifacts = adapter.build('win-x64', web, root / 'run',
                    {'app_name': '中文 游戏', 'app_id': 'com.example.game', 'allow_dependency_install': True}, lambda *_: None, threading.Event())
            self.assertEqual(len(artifacts), 1)
            self.assertIn('--ignore-scripts', commands[0])
            self.assertIn('--publish', commands[1])
            self.assertIn('never', commands[1])
            package = json.loads((root / 'run/win-x64/package.json').read_text())
            self.assertNotIn('scripts', package)
            self.assertEqual(package['build']['productName'], '中文 游戏')

    def test_source_symlink_and_missing_sdk_are_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source'
            source.mkdir()
            (source / 'leak').symlink_to('/etc/passwd')
            adapter = LocalExportAdapter()
            with self.assertRaises(ExportBlocked):
                adapter._copy_source(source, Path(temporary) / 'copy', threading.Event())
            with patch.object(adapter, 'capabilities', return_value={'android_sdk': None, 'java': None}):
                with self.assertRaises(ExportBlocked):
                    adapter._android_tools(lambda *_: None, threading.Event(), Path(temporary))

    def test_cancel_before_process_start(self):
        event = threading.Event()
        event.set()
        with self.assertRaises(ExportCancelled):
            LocalExportAdapter()._run(['not-executed'], Path('.'), lambda *_: None, event, 'test')

    def test_electron_security_and_local_origin(self):
        self.assertIn('css:{postcss:{plugins:[]}}', VITE_CONFIG)
        self.assertIn('sandbox:true,contextIsolation:true,nodeIntegration:false', ELECTRON_MAIN)
        self.assertIn('game://local/index.html', ELECTRON_MAIN)
        self.assertIn('pathToFileURL(real)', ELECTRON_MAIN)
        self.assertIn('decodeURIComponent', ELECTRON_MAIN)
        self.assertNotIn('localhost:', ELECTRON_MAIN)
        self.assertTrue(desktop_package('Game', 'com.example.game')['build']['asar'])

    def test_dependency_download_requires_explicit_setting(self):
        with self.assertRaises(ExportBlocked):
            LocalExportAdapter._dependency_authorization({})

    def test_artifact_absence_is_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ExportBuildError):
                LocalExportAdapter._artifacts(Path(temporary), '*.zip')
