"""Export conversation stays typed and uses the configured provider."""
import unittest
from types import SimpleNamespace
from sceneops_ai_agents.export_agent import ExportAgent


class Provider:
    def __init__(self, action=None):
        self.action = action
        self.calls = []

    def settings(self):
        return SimpleNamespace(provider='openai-compatible', model='selected-model')

    async def generate(self, prompt, **options):
        self.calls.append((prompt, options))
        return SimpleNamespace(provider='openai-compatible', model='selected-model',
            usage={'total_tokens': 123}, latency_ms=1, text='',
            structured={'content': '将重新打包，请以执行记录为准。',
                'actions': [self.action] if self.action else []})


class Preparation:
    def __init__(self):
        self.calls = []

    async def prepare(self, request):
        self.calls.append(request)
        return SimpleNamespace(model_dump=lambda **_kwargs: {
            'status': 'succeeded', 'recommendation': {'assets': [], 'experiences': [
                {'candidate_id': 'android-signing', 'revision': 3, 'purpose': '导出',
                 'adoption': 'reference', 'reason': '平台匹配'}], 'skills': [],
                'production_advice': [], 'conflicts': [], 'gaps': []},
            'call': {'status': 'succeeded', 'usage': {'total_tokens': 7}}})

    async def selected_context(self, request, result):
        return {'status': 'succeeded', 'recommendation': result.model_dump()['recommendation'],
                'selected_details': [{'identity': {'candidate_id': 'android-signing'},
                                      'content': {'body': 'Android 签名与包检查'}}]}


def task():
    return dict(id='export-test', project_id='project-test', source_version='snapshot-test',
        settings={}, messages=[], platforms=[dict(platform='android', status='failed',
        verification='pending', attempts=[dict(id='a', status='failed', stage='build',
            error='secret-value', logs=[])])])


class ExportAgentTests(unittest.TestCase):
    def test_one_bounded_call_with_redacted_context_and_audit(self):
        provider = Provider({'action': 'continue', 'platform': 'android'})
        preparation = Preparation()
        result = ExportAgent(provider, redact=lambda s: s.replace('secret-value', '[redacted]'),
                             production_preparation=preparation)(
            task(), '继续导出')
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(len(preparation.calls), 1)
        self.assertEqual(preparation.calls[0].production_kind, 'export')
        self.assertNotIn('secret-value', provider.calls[0][0])
        self.assertIn('Android 签名与包检查', provider.calls[0][0])
        self.assertNotIn('角色素材', provider.calls[0][0])
        self.assertEqual(result['usage']['total_tokens'], 130)
        self.assertEqual(result['usage']['production_preparation']['total_tokens'], 7)
        self.assertEqual(result['agent_task_id'], 'export-agent:export-test')
        self.assertIn('invocation', result)

    def test_model_cannot_add_arbitrary_command(self):
        provider = Provider({'action': 'continue', 'platform': 'android', 'command': 'bad'})
        with self.assertRaises(ValueError):
            ExportAgent(provider)(task(), '修复')

    def test_model_cannot_select_unrequested_platform(self):
        with self.assertRaises(ValueError):
            ExportAgent(Provider({'action': 'continue', 'platform': 'win-x64'}))(task(), '继续')

    def test_provider_change_does_not_make_a_call(self):
        provider = Provider()
        with self.assertRaises(ValueError):
            ExportAgent(provider)(task(), '分析', 'codexcli')
        self.assertEqual(provider.calls, [])


if __name__ == '__main__':
    unittest.main()
