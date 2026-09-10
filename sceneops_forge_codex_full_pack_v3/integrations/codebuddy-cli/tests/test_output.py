"""Focused parser regressions; no subprocess, network, model or business effects."""
import json
import unittest

from sceneops_codebuddy.provider import CodeBuddyFailure, _arguments, _parse_output, _structured_result


class OutputTests(unittest.TestCase):
    def parse(self, value):
        return _parse_output(json.dumps(value).encode())

    def test_single_result_remains_supported(self):
        result = {'type': 'result', 'subtype': 'success', 'result': 'ok'}
        self.assertEqual(self.parse(result), result)

    def test_transcript_returns_only_final_result_with_metadata(self):
        result = {'type': 'result', 'subtype': 'success', 'is_error': False,
                  'result': 'ok', 'usage': {'input_tokens': 1},
                  'structured_output': {'status': 'ok'}}
        self.assertEqual(self.parse([{'type': 'message', 'role': 'user'},
                                    {'type': 'reasoning', 'content': 'private'}, result]), result)

    def test_incomplete_or_ambiguous_transcripts_are_rejected(self):
        result = {'type': 'result', 'result': 'ok'}
        for value in ([], [{'type': 'message'}], [result, result],
                      [result, {'type': 'message'}], ['ok', result], None, 'ok'):
            with self.subTest(value=value), self.assertRaises(CodeBuddyFailure) as caught:
                self.parse(value)
            self.assertEqual(caught.exception.code, 'CLI_INVALID_RESPONSE')

    def test_turn_limit_is_not_success(self):
        with self.assertRaises(CodeBuddyFailure) as caught:
            self.parse([{'type': 'result', 'subtype': 'error_max_turns', 'is_error': True}])
        self.assertEqual(caught.exception.code, 'CLI_TURN_LIMIT')

    def test_failure_uses_result_not_user_words(self):
        with self.assertRaises(CodeBuddyFailure) as caught:
            self.parse([{'type': 'message', 'content': 'unauthorized 401'},
                        {'type': 'result', 'is_error': True, 'result': 'quota exceeded'}])
        self.assertEqual(caught.exception.code, 'CLI_RATE_LIMITED')

    def test_invalid_json_is_not_exposed(self):
        with self.assertRaises(CodeBuddyFailure) as caught:
            _parse_output(b'private-invalid-output')
        self.assertNotIn('private', str(caught.exception))

    def test_chat_has_no_tools_and_default_model_is_omitted(self):
        args = _arguments('cli-default', None)
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertNotIn('--model', args)
        self.assertNotIn('--json-schema', args)
        self.assertEqual(args[args.index('--effort') + 1], 'low')

    def test_reasoning_effort_is_forwarded_and_validated(self):
        args = _arguments('glm-5.3-flash', None, effort='xhigh')
        self.assertEqual(args[args.index('--effort') + 1], 'xhigh')
        with self.assertRaises(CodeBuddyFailure) as caught:
            _arguments('glm-5.3-flash', None, effort='unsupported')
        self.assertEqual(caught.exception.code, 'CLI_EFFORT_INVALID')

    def test_structured_request_keeps_tools_disabled(self):
        schema = {'type': 'object', 'properties': {'status': {'type': 'string'}}}
        args = _arguments('glm-5.3-flash', schema)
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertEqual(args[args.index('--mcp-config') + 1], '{"mcpServers":{}}')
        self.assertEqual(args[args.index('--permission-mode') + 1], 'default')
        self.assertIn('--strict-mcp-config', args)
        self.assertIn('--no-session-persistence', args)
        self.assertNotIn('--json-schema', args)
        self.assertIn('应用输出合同', args[args.index('--system-prompt') + 1])

    def test_structured_json_must_match_schema_without_repairs(self):
        schema = {'type': 'object', 'properties': {'status': {'type': 'string'}},
                  'required': ['status'], 'additionalProperties': False}
        result = _structured_result(self.parse([{'type': 'result', 'result': '{"status":"ok"}'}]), schema)
        self.assertEqual(result['structured_output'], {'status': 'ok'})
        for text in ('```json\n{"status":"ok"}\n```', '{}', '{"status":1}',
                     '{"status":"ok","extra":true}', '[]'):
            with self.subTest(text=text), self.assertRaises(CodeBuddyFailure) as caught:
                _structured_result({'result': text}, schema)
            self.assertEqual(caught.exception.code, 'CLI_STRUCTURED_INVALID')

    def test_nonfinite_numbers_are_not_json(self):
        schema = {'type': 'object', 'properties': {'value': {'type': 'number'}}}
        for constant in ('NaN', 'Infinity', '-Infinity'):
            with self.subTest(constant=constant), self.assertRaises(CodeBuddyFailure):
                _structured_result({'result': '{"value":' + constant + '}'}, schema)


if __name__ == '__main__':
    unittest.main()
