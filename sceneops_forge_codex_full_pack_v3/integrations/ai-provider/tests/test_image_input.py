"""Deterministic reference-image transport contracts; no model is invoked."""
import tempfile
import unittest
from pathlib import Path

from sceneops_ai_provider import ProviderFailure, ProviderService
from sceneops_ai_provider import codex_cli
from sceneops_ai_provider.openai_compatible import build_payload


class ImageInputTests(unittest.IsolatedAsyncioTestCase):
    def test_model_support_is_not_inferred_for_arbitrary_compatible_catalogues(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'settings.sqlite3')
            self.assertEqual(service.image_input_support(), 'unsupported')
            service.update_settings(provider='codexcli', model='fixture-codex')
            self.assertEqual(service.image_input_support(), 'supported')
            service.update_settings(provider='openai-compatible', model='arbitrary-model',
                                    base_url='https://example.com/v1', api_key='fixture-secret')
            self.assertEqual(service.image_input_support(), 'unknown')

    def test_codex_places_each_reference_before_stdin_prompt(self):
        first = Path("/tmp/sceneops-reference-one.png")
        second = Path("/tmp/sceneops-reference-two.webp")
        arguments = codex_cli._arguments(image_paths=(first, second))
        self.assertEqual(arguments[-1], "-")
        self.assertEqual(
            [(arguments[index + 1]) for index, item in enumerate(arguments) if item == "--image"],
            [str(first), str(second)],
        )

    def test_openai_payloads_encode_reference_as_image_content(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "reference.png"
            image.write_bytes(b"fixture-image")
            chat = build_payload("chat-completions", "make a tree", "vision-model", None, [image])
            chat_image = chat["messages"][1]["content"][1]
            self.assertEqual(chat_image["type"], "image_url")
            self.assertTrue(chat_image["image_url"]["url"].startswith("data:image/png;base64,"))

            responses = build_payload("responses", "make a tree", "vision-model", None, [image])
            response_image = responses["input"][0]["content"][1]
            self.assertEqual(response_image["type"], "input_image")
            self.assertTrue(response_image["image_url"].startswith("data:image/png;base64,"))

    async def test_codebuddy_reference_image_fails_before_model_invocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "reference.jpg"
            image.write_bytes(b"fixture-image")
            service = ProviderService(root / "settings.sqlite3")
            with self.assertRaises(ProviderFailure) as failure:
                await service.generate("make a tree", images=[image])
            self.assertEqual(failure.exception.code, "CLI_IMAGE_INPUT_UNSUPPORTED")
            self.assertEqual(failure.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
