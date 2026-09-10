"""One isolated provider-switch smoke; never invokes a real model or user settings."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sceneops_ai_provider import ProviderService
from sceneops_ai_provider.service import SYSTEM_PROMPT


class ProviderSwitchSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_codex_discovery_is_cached_for_the_model_picker(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'settings.sqlite3')
            with patch('sceneops_ai_provider.codex_cli.list_models', new=AsyncMock(
                    return_value=[('gpt-a', 'GPT A'), ('gpt-b', 'GPT B')])):
                discovered = await service.discover_models(provider='codexcli')
            self.assertEqual([item.id for item in discovered], ['cli-default', 'gpt-a', 'gpt-b'])
            self.assertIn(('gpt-a', 'GPT A'), [(item.id, item.label) for item in service.models()
                                               if item.provider == 'codexcli'])

    async def test_round_trip_keeps_models_and_routes_codex(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'settings.sqlite3')
            buddy = service.settings()
            self.assertEqual(buddy.provider, 'codebuddycli')
            service.update_settings(provider='codexcli', model='my-codex-model')
            service.update_settings(provider='codebuddycli')
            self.assertEqual(service.settings().model, buddy.model)
            service.update_settings(provider='openai-compatible', model='my-oai-model')
            service.update_settings(provider='codexcli')
            self.assertEqual(service.settings().model, 'my-codex-model')
            self.assertIn(('codexcli', 'my-codex-model'), [(m.provider, m.id) for m in service.models()])
            with patch('sceneops_ai_provider.codex_cli.invoke_json', new_callable=AsyncMock,
                       return_value={'result': 'fixture reply', 'usage': {'input_tokens': 2, 'output_tokens': 3}}) as invoke:
                result = await service.generate('fixture prompt')
            self.assertEqual((result.provider, result.model, result.text), ('codexcli', 'my-codex-model', 'fixture reply'))
            invoke.assert_awaited_once_with('fixture prompt', 'my-codex-model', schema=None, timeout=120,
                                            system_prompt=SYSTEM_PROMPT)
            service.update_settings(provider='openai-compatible')
            self.assertEqual(service.settings().model, 'my-oai-model')


if __name__ == '__main__':
    unittest.main()
