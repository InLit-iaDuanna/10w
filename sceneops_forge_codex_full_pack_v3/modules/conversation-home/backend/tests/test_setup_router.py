"""Local host execution boundaries use deterministic HTTP requests."""
import unittest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request
from conversation_home.setup_router import InstallRequest, require_local_request


def request(host='127.0.0.1', origin='http://localhost:4300'):
    return Request({'type': 'http', 'client': (host, 1234),
                    'headers': [(b'origin', origin.encode())]})


class SetupRouterTests(unittest.TestCase):
    def test_loopback_origin_allowed(self):
        require_local_request(request())

    def test_remote_peer_and_origin_rejected(self):
        for value in (request(host='192.0.2.1'), request(origin='https://example.com'), request(origin='null')):
            with self.assertRaises(HTTPException) as error:
                require_local_request(value)
            self.assertEqual(error.exception.status_code, 403)

    def test_unknown_provider_and_freeform_rejected(self):
        for value in ({'providers': ['bash']}, {'providers': []},
                      {'providers': ['codexcli'], 'command': 'echo forbidden'}):
            with self.assertRaises(ValidationError):
                InstallRequest.model_validate(value)
