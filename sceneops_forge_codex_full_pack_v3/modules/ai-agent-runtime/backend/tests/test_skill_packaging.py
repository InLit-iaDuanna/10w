"""Build with the declared backend and load resources from the wheel, not cwd."""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class SkillPackagingTests(unittest.TestCase):
    def test_wheel_resources_reach_provider_from_an_unrelated_directory(self):
        from hatchling.builders.wheel import WheelBuilder
        backend = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            wheel = next(WheelBuilder(str(backend)).build(directory=directory, versions=["standard"]))
            env = dict(os.environ)
            paths = [path for path in env.get("PYTHONPATH", "").split(os.pathsep)
                     if path and Path(path).resolve() != backend / "src"]
            env["PYTHONPATH"] = os.pathsep.join([wheel, *paths])
            script = '''
import asyncio
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace
from sceneops_ai_agents import AgentRuntime
from sceneops_ai_agents.task_models import NextActionInput
import sceneops_ai_agents
assert '.whl/' in sceneops_ai_agents.__file__, sceneops_ai_agents.__file__
class Provider:
    database_path = Path('fixture.sqlite3')
    def settings(self):
        return SimpleNamespace(provider='fixture', model='fixture')
    async def generate(self, prompt, **kwargs):
        self.request = kwargs
        return SimpleNamespace(provider='fixture', model='fixture', latency_ms=0, usage=None,
            structured={'action_id':'inspect', 'capability_id':'code.workspace.inspect',
                        'rationale':'fixture', 'inputs':{}})
provider = Provider()
data = NextActionInput(goal='增加冲刺冷却', history=[], observations={},
    capabilities=[{'id':'code.file.write'}], expected_provider='fixture', expected_model='fixture')
result = asyncio.run(AgentRuntime(provider).next_action(
    SimpleNamespace(id='packaged', inputs=data.model_dump()),
    SimpleNamespace(raise_if_cancelled=lambda: None)))
root = files('sceneops_ai_agents').joinpath('skills')
for name in ('gameplay', 'debug', 'qa'):
    assert root.joinpath(f'sceneops-threejs-{name}/SKILL.md').read_text(encoding='utf-8')
for path in ('sceneops-threejs-gameplay/SKILL.md',
             'sceneops-threejs-gameplay/references/time-and-state.md'):
    body = root.joinpath(path).read_text(encoding='utf-8')
    assert provider.request['instructions'].count(body) == 1
assert 'Copyright (c) 2026 Majid Manzarpour' in root.joinpath('LICENSE').read_text()
assert provider.request['purpose'] == 'agent-action'
assert not any('UNAVAILABLE' in line for line in result.logs)
'''
            result = subprocess.run([sys.executable, "-c", script], cwd=directory, env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
