"""Injectable HTTP transport for ComfyUI."""

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .errors import TransportFailure


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes
    content_type: str = "application/json"

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


class JsonTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        body: Optional[Dict[str, Any]],
        timeout_seconds: float,
    ) -> HttpResponse:
        ...


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


class UrllibJsonTransport:
    def __init__(self, max_response_bytes: int = 128 * 1024 * 1024) -> None:
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        self._max_response_bytes = max_response_bytes
        self._opener = build_opener(_NoRedirectHandler())

    def request(
        self,
        method: str,
        url: str,
        body: Optional[Dict[str, Any]],
        timeout_seconds: float,
    ) -> HttpResponse:
        encoded = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if encoded is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=encoded, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                content = response.read(self._max_response_bytes + 1)
                if len(content) > self._max_response_bytes:
                    raise TransportFailure("ComfyUI response exceeded configured byte limit")
                return HttpResponse(
                    status_code=response.status,
                    body=content,
                    content_type=response.headers.get_content_type(),
                )
        except HTTPError as exc:
            content = exc.read(self._max_response_bytes + 1)
            if len(content) > self._max_response_bytes:
                raise TransportFailure("ComfyUI error response exceeded configured byte limit")
            return HttpResponse(
                status_code=exc.code,
                body=content,
                content_type=exc.headers.get_content_type(),
            )
        except (URLError, TimeoutError, OSError) as exc:
            raise TransportFailure(str(exc)) from exc
