"""Bounded generated-protocol tests; browser integration belongs to the executor."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from sceneops_project_workspace.game_projects import template_files
from sceneops_project_workspace.test_adapter_files import test_adapter_files


class GameTestAdapterTests(unittest.TestCase):
    def test_real_protocol_reset_pause_and_unknown_state(self):
        source = test_adapter_files()['src/game/sceneops-test.ts']
        assertions = Path(__file__).with_name('game_test_adapter_assertions.ts').read_text()
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'protocol.mts'
            script.write_text(source + '\n' + assertions)
            result = subprocess.run(
                ['node', '--experimental-strip-types', str(script)],
                text=True, capture_output=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_templates_bind_only_explicit_test_mode_and_keep_original_loops(self):
        for architecture in ('object-component', 'ecs'):
            with self.subTest(architecture=architecture):
                files = template_files(architecture)
                entry = files['src/game/Game.ts' if architecture == 'object-component' else 'src/main.ts']
                self.assertIn("if (import.meta.env.MODE === 'sceneops-test')", entry)
                self.assertIn('window.__sceneopsTest = ', entry)
                self.assertIn('requestAnimationFrame(', entry)
                self.assertIn('renderer.render(', entry)
                self.assertIn('performance.now()', entry)
                self.assertNotIn('advance(', entry)
                self.assertNotIn('step(', files['src/game/sceneops-test.ts'])
                self.assertIn('dataset.playerX', entry)
                self.assertIn('dataset.playerZ', entry)
        ecs = template_files('ecs')['src/main.ts']
        self.assertIn('inputSystem(game.world, keys); movementSystem(game.world, delta); collectionSystem(game.world, scoreOutput)', ecs)


if __name__ == '__main__':
    unittest.main()
