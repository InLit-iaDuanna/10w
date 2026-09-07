"""Purpose-to-system-instruction routing without provider or network calls."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from sceneops_ai_provider import ProviderService, codex_cli
from sceneops_ai_provider.openai_compatible import build_payload
from sceneops_ai_provider.service import ACTION_SELECTION_PROMPT, SYSTEM_PROMPT, instructions_for_purpose
from sceneops_codebuddy.provider import _arguments as codebuddy_arguments


class PromptRoutingTests(unittest.TestCase):
    def test_discussion_and_action_selection_have_distinct_system_instructions(self):
        self.assertEqual(instructions_for_purpose("chat"), SYSTEM_PROMPT)
        self.assertEqual(instructions_for_purpose("agent-action"), ACTION_SELECTION_PROMPT)
        self.assertNotEqual(SYSTEM_PROMPT, ACTION_SELECTION_PROMPT)

    def test_selected_instruction_reaches_both_compatible_protocols(self):
        instruction = "trusted fixture instruction"
        chat = build_payload("chat-completions", "hello", "model", None, [], instruction)
        responses = build_payload("responses", "hello", "model", None, [], instruction)
        self.assertEqual(chat["messages"][0]["content"], instruction)
        self.assertEqual(responses["instructions"], instruction)

    def test_selected_instruction_reaches_both_restricted_cli_transports(self):
        instruction = "trusted fixture instruction"
        codebuddy = codebuddy_arguments("cli-default", None, system_prompt=instruction)
        codex = codex_cli._arguments(system_prompt=instruction)
        self.assertEqual(codebuddy[codebuddy.index("--system-prompt") + 1], instruction)
        developer = next(value for value in codex if value.startswith("developer_instructions="))
        self.assertIn(instruction, developer)


class ProviderPurposeTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_service_forwards_the_action_purpose_to_cli_instructions(self):
        with TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / "state.sqlite3")
            response = {"result": "{}", "structured_output": {}}
            with patch("sceneops_ai_provider.service.cli_invoke_json",
                       new=AsyncMock(return_value=response)) as invoke:
                await service.generate("choose", schema={"type": "object"},
                                       purpose="agent-action")
        self.assertEqual(invoke.await_args.kwargs["system_prompt"], ACTION_SELECTION_PROMPT)


if __name__ == "__main__":
    unittest.main()
