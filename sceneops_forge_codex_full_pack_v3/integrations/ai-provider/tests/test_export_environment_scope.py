"""Environment setup is a trusted native export capability, never a chat default."""
import json
import unittest
from sceneops_ai_provider import codex_cli


class ExportEnvironmentScopeTests(unittest.TestCase):
    def test_export_scope_selects_system_setup_without_enabling_unrelated_tools(self):
        args = codex_cli._arguments(full_access=True, authorized_scope='本次安卓导出与SDK补齐',
                                    allow_environment_setup=True)
        prompt = json.loads(next(arg.split('=', 1)[1] for arg in args
                                 if arg.startswith('developer_instructions=')))
        self.assertIn(codex_cli.EXPORT_AGENT_PROMPT, prompt)
        self.assertNotIn(codex_cli.AGENT_PROMPT, prompt)
        self.assertIn('features.shell_tool=true', args)
        self.assertIn('features.plugins=false', args)
        self.assertIn('orchestrator.mcp.enabled=false', args)

    def test_ordinary_native_and_readonly_keep_existing_permissions(self):
        args = codex_cli._arguments(full_access=True, authorized_scope='普通游戏制作')
        prompt = json.loads(next(arg.split('=', 1)[1] for arg in args
                                 if arg.startswith('developer_instructions=')))
        self.assertIn(codex_cli.AGENT_PROMPT, prompt)
        self.assertIn('features.shell_tool=false', codex_cli._arguments())
        with self.assertRaises(codex_cli.CodexFailure):
            codex_cli._arguments(allow_environment_setup=True)


if __name__ == '__main__':
    unittest.main()
