"""Maintenance cases only; not executed under the current smoke-only authorization."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sceneops_ai_provider import ProviderService, ProviderFailure


class EndpointSecretsTests(unittest.TestCase):
    def test_new_endpoint_does_not_receive_existing_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / "app.sqlite3")
            service.update_settings(provider="openai-compatible", model="test-model",
                base_url="https://one.example/v1", api_key="test-only-secret")
            changed = service.update_settings(base_url="https://two.example/v1")
            self.assertFalse(changed.api_key_configured)
            restored = service.update_settings(base_url="https://one.example/v1")
            self.assertTrue(restored.api_key_configured)
            self.assertNotIn("test-only-secret", repr(restored))

    def test_secret_write_failure_does_not_publish_new_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / "app.sqlite3")
            service.update_settings(provider="openai-compatible", model="test-model",
                base_url="https://one.example/v1", api_key="test-only-secret")
            with patch.object(service, "_write_api_key", side_effect=ProviderFailure("WRITE_FAILED", "not writable")):
                with self.assertRaises(ProviderFailure):
                    service.update_settings(base_url="https://two.example/v1", api_key="new-test-only-secret")
            self.assertEqual(service.settings().base_url, "https://one.example/v1")
            self.assertTrue(service.settings().api_key_configured)
