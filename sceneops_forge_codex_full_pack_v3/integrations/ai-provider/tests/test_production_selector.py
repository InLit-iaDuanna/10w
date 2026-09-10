"""Independent production-selector settings and exact-route generation contracts."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sceneops_ai_provider import ProviderCompletion, ProviderFailure, ProviderService


class ProductionSelectorSettingsTests(unittest.TestCase):
    def test_legacy_settings_migrate_with_selector_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'settings.sqlite3'
            with sqlite3.connect(database) as connection:
                connection.execute('''CREATE TABLE conversation_ai_settings (
                    id INTEGER PRIMARY KEY CHECK(id=1), model TEXT NOT NULL)''')
                connection.execute('INSERT INTO conversation_ai_settings VALUES(1,?)',
                                   ('legacy-model',))

            settings = ProviderService(database).settings()

        self.assertEqual((settings.provider, settings.model), ('codebuddycli', 'legacy-model'))
        self.assertIsNone(settings.selector_provider)
        self.assertIsNone(settings.selector_model)

    def test_selector_round_trip_does_not_change_main_route_and_can_be_cleared(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'settings.sqlite3'
            service = ProviderService(database)
            service.update_settings(provider='codexcli', model='main-model')

            saved = service.update_settings(selector_provider='codexcli',
                                            selector_model='economy-model')
            snapshot = ProviderService(database).selector_settings()

            self.assertEqual((saved.provider, saved.model), ('codexcli', 'main-model'))
            self.assertEqual((saved.selector_provider, saved.selector_model),
                             ('codexcli', 'economy-model'))
            self.assertEqual((snapshot.provider, snapshot.model),
                             ('codexcli', 'economy-model'))

            cleared = service.update_settings(update_selector=True)
            self.assertIsNone(cleared.selector_provider)
            self.assertIsNone(service.selector_settings())

    def test_partial_selector_route_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'settings.sqlite3')
            with self.assertRaises(ProviderFailure) as failure:
                service.update_settings(selector_provider='codexcli')
        self.assertEqual(failure.exception.code, 'SELECTOR_SETTINGS_INCOMPLETE')


class ProductionSelectorGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_selector_never_uses_main_model(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'settings.sqlite3')
            with patch.object(service, '_cli_generate', new=AsyncMock()) as invoke:
                with self.assertRaises(ProviderFailure) as failure:
                    await service.generate_for_selector('choose')
        self.assertEqual(failure.exception.code, 'SELECTOR_MODEL_NOT_CONFIGURED')
        invoke.assert_not_awaited()

    async def test_selector_uses_frozen_route_once_without_mutating_main_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'settings.sqlite3')
            service.update_settings(provider='codexcli', model='main-model',
                                    selector_provider='codexcli', selector_model='economy-model')
            snapshot = service.selector_settings()
            service.update_settings(selector_provider='codexcli', selector_model='new-selector')
            response = {'result': '{"selected":true}',
                        'structured_output': {'selected': True}}
            with patch('sceneops_ai_provider.codex_cli.invoke_json',
                       new=AsyncMock(return_value=response)) as invoke:
                completion = await service.generate_for_selector(
                    'choose', schema={'type': 'object'}, snapshot=snapshot)

            self.assertEqual((completion.provider, completion.model),
                             ('codexcli', 'economy-model'))
            self.assertEqual((service.settings().provider, service.settings().model),
                             ('codexcli', 'main-model'))
            invoke.assert_awaited_once()
            self.assertEqual(invoke.await_args.args[:2], ('choose', 'economy-model'))
            self.assertEqual(invoke.await_args.kwargs['timeout'], 30)

    async def test_compatible_selector_reuses_exact_endpoint_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'settings.sqlite3')
            service.update_settings(
                base_url='https://selector.example/v1', api_key='fixture-selector-secret',
                api_protocol='responses', selector_provider='openai-compatible',
                selector_model='economy-model')
            completion = ProviderCompletion(
                text='{}', provider='openai-compatible', model='economy-model',
                latency_ms=1, structured={})
            with patch('sceneops_ai_provider.openai_compatible.generate_completion',
                       new=AsyncMock(return_value=completion)) as generate:
                result = await service.generate_for_selector('choose')

        self.assertEqual(result, completion)
        generate.assert_awaited_once()
        self.assertEqual(generate.await_args.kwargs['base_url'],
                         'https://selector.example/v1')
        self.assertEqual(generate.await_args.kwargs['api_key'], 'fixture-selector-secret')
        self.assertEqual(generate.await_args.kwargs['api_protocol'], 'responses')

    async def test_mismatched_transport_result_is_rejected_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'settings.sqlite3')
            service.update_settings(selector_provider='codexcli',
                                    selector_model='economy-model')
            wrong = ProviderCompletion(text='{}', provider='codexcli',
                                       model='different-model', latency_ms=1)
            with patch.object(service, '_cli_generate',
                              new=AsyncMock(return_value=wrong)) as generate:
                with self.assertRaises(ProviderFailure) as failure:
                    await service.generate_for_selector('choose')

        self.assertEqual(failure.exception.code, 'SELECTOR_ROUTE_MISMATCH')
        generate.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
