"""Regression checks for model audit events; no provider calls are made."""
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sceneops_ai_provider.service import ProviderCompletion, ProviderService, _audit_model


class ModelAuditTests(unittest.TestCase):
    def test_stream_payload_can_use_event_field(self):
        with self.assertLogs('sceneops.ai', level='INFO') as captured:
            _audit_model('model.stream_event', call_id='fixture',
                         event={'type': 'text_delta', 'text': 'OK'})

        record = captured.records[0]
        self.assertEqual(record.sceneops_audit['event'], 'model.stream_event')
        self.assertEqual(record.sceneops_audit['fields']['event'],
                         {'type': 'text_delta', 'text': 'OK'})


class ConnectionAuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_streamed_connection_check_survives_audit_callback(self):
        async def complete(*args, **kwargs):
            await args[4]({'type': 'text_delta', 'text': 'OK'})
            return ProviderCompletion(text='OK', provider='codebuddycli',
                                      model='cli-default', latency_ms=1)

        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'settings.sqlite3')
            with patch.object(service, '_cli_generate', new=AsyncMock(side_effect=complete)):
                result = await service.check_connection(
                    provider='codebuddycli', model='cli-default', streaming=True)

        self.assertTrue(result.streaming)
        self.assertIn('连接成功', result.message)


if __name__ == '__main__':
    unittest.main()
