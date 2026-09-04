"""Maintained failure coverage; not run / pending approval."""
import unittest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException
from sceneops_design_ai import AiRequest, AiSuggestion, ModelCatalog
from sceneops_design_ai.codebuddy import suggest

class CodeBuddyFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_output_does_not_become_suggestion(self):
        current = AiSuggestion(title='门', goal='开门', playerValue='通行', given='有钥匙', when='交互', then='开启')
        with patch('sceneops_design_ai.codebuddy.invoke_json', new=AsyncMock(return_value={'structured_output': {'invalid': 'fixture'}})):
            with self.assertRaises(HTTPException) as raised:
                await suggest(AiRequest(model='hy3', brief='开门功能', current=current))
        self.assertEqual(raised.exception.status_code, 502)
