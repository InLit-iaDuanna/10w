"""Bounded OpenAI-compatible SSE parsing for supported text protocols."""
from __future__ import annotations

import asyncio
import json
import time

import httpx

from .service import ApiProtocol, ProviderCompletion, ProviderFailure, _safe_usage

MAX_OUTPUT_BYTES = 4 * 1024 * 1024


async def _events(response):
    pending, data, size = b'', [], 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_OUTPUT_BYTES:
            raise ProviderFailure('OPENAI_OUTPUT_LIMIT',
                                  '兼容服务回复超过本次输出限制，未采用该结果。')
        pending += chunk
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            line = line.rstrip(b'\r')
            if not line:
                if data:
                    yield b'\n'.join(data).decode('utf-8')
                    data = []
            elif line.startswith(b'data:'):
                data.append(line[5:].removeprefix(b' '))
    # An unterminated event is incomplete, never an authoritative final reply.


def _check_response(response, api_protocol: ApiProtocol):
    if response.is_redirect:
        raise ProviderFailure('OPENAI_REDIRECT_REJECTED',
                              '兼容服务返回了重定向；请直接配置最终 HTTPS 地址。')
    if response.status_code in (401, 403):
        raise ProviderFailure('OPENAI_AUTH_FAILED',
                              '兼容服务拒绝了凭据，请重新配置 API Key 或检查权限。')
    if response.status_code == 429:
        raise ProviderFailure('OPENAI_RATE_LIMITED',
                              '兼容服务达到速率或额度限制，请稍后手动重试。')
    if response.status_code == 404 and api_protocol == 'responses':
        raise ProviderFailure('OPENAI_RESPONSES_UNAVAILABLE',
                              '兼容服务没有提供 Responses API；请检查地址或改用 Chat Completions。')
    if response.status_code >= 500:
        raise ProviderFailure('OPENAI_SERVICE_ERROR',
                              f'兼容服务暂时不可用（HTTP {response.status_code}）。')
    if response.status_code >= 400:
        raise ProviderFailure('OPENAI_REQUEST_REJECTED',
                              f'兼容服务拒绝请求（HTTP {response.status_code}）；请检查模型与接口设置。')
    content_type = response.headers.get('content-type', '').split(';')[0].strip()
    if content_type != 'text/event-stream':
        raise ProviderFailure('OPENAI_STREAM_UNSUPPORTED',
                              '兼容服务未返回 SSE 流，请检查服务的流式支持。')


def _structured(text: str, schema: dict | None) -> dict | None:
    if schema is None:
        return None
    try:
        value = json.loads(text)
    except ValueError as error:
        raise ProviderFailure('OPENAI_STRUCTURED_INVALID',
                              '兼容服务未按请求返回有效 JSON 对象。') from error
    if not isinstance(value, dict):
        raise ProviderFailure('OPENAI_STRUCTURED_INVALID', '兼容服务返回的结构化结果不是对象。')
    return value


def _response_text(response: object) -> str:
    if not isinstance(response, dict) or response.get('status') != 'completed':
        raise ValueError('Response not completed')
    output = response.get('output')
    if not isinstance(output, list):
        raise ValueError('Invalid output')
    values: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get('type') != 'message':
            continue
        content = item.get('content')
        if isinstance(content, list):
            values.extend(part['text'] for part in content
                          if isinstance(part, dict) and part.get('type') == 'output_text'
                          and isinstance(part.get('text'), str))
    text = ''.join(values)
    if not text.strip():
        raise ValueError('Missing output text')
    return text


async def _chat_events(response, on_event):
    content, usage, finished = [], None, False
    async for data in _events(response):
        if data == '[DONE]':
            finished = True
            break
        event = json.loads(data)
        if not isinstance(event, dict) or event.get('error'):
            raise ValueError('Invalid completion event')
        usage = _safe_usage(event.get('usage')) or usage
        choices = event.get('choices', [])
        if not isinstance(choices, list):
            raise ValueError('Invalid choices')
        for choice in choices:
            if not isinstance(choice, dict) or choice.get('index') != 0:
                continue
            delta = choice.get('delta', {})
            if not isinstance(delta, dict):
                raise ValueError('Invalid delta')
            text = delta.get('content')
            if isinstance(text, str) and text:
                content.append(text)
                await on_event({'type': 'text_delta', 'text': text})
    text = ''.join(content)
    if not finished or not text.strip():
        raise ValueError('Incomplete chat completion')
    return text, usage


async def _response_events(response, on_event):
    content, final_response = [], None
    async for data in _events(response):
        event = json.loads(data)
        if not isinstance(event, dict):
            raise ValueError('Invalid response event')
        event_type = event.get('type')
        if event_type == 'response.output_text.delta':
            delta = event.get('delta')
            if not isinstance(delta, str) or not delta:
                raise ValueError('Invalid text delta')
            content.append(delta)
            await on_event({'type': 'text_delta', 'text': delta})
        elif event_type == 'response.completed':
            final_response = event.get('response')
            break
        elif event_type in ('response.failed', 'response.incomplete', 'error'):
            raise ProviderFailure('OPENAI_RESPONSE_FAILED',
                                  '兼容服务未完成本次 Response，请检查模型与服务状态。')
    final_text = _response_text(final_response)
    if ''.join(content) != final_text:
        raise ValueError('Streamed text does not match completed response')
    usage = _safe_usage(final_response.get('usage')) if isinstance(final_response, dict) else None
    return final_text, usage


async def stream_completion(*, endpoint: str, api_key: str,
                            api_protocol: ApiProtocol, payload: dict,
                            timeout: float, started: float, schema: dict | None,
                            on_event) -> ProviderCompletion:
    try:
        async with asyncio.timeout(timeout):
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                         trust_env=False) as client:
                async with client.stream('POST', endpoint, headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                }, json={**payload, 'stream': True}) as response:
                    _check_response(response, api_protocol)
                    if api_protocol == 'responses':
                        text, usage = await _response_events(response, on_event)
                    else:
                        text, usage = await _chat_events(response, on_event)
    except ProviderFailure:
        raise
    except (httpx.TimeoutException, TimeoutError) as error:
        raise ProviderFailure('OPENAI_TIMEOUT',
                              'OpenAI 兼容服务请求超时，请检查服务状态后重试。') from error
    except httpx.RequestError as error:
        raise ProviderFailure('OPENAI_NETWORK_ERROR',
                              '无法连接 OpenAI 兼容服务，请检查地址、网络或本机服务。') from error
    except (ValueError, UnicodeError) as error:
        label = 'Responses API' if api_protocol == 'responses' else 'Chat Completions'
        raise ProviderFailure('OPENAI_INVALID_RESPONSE',
                              f'兼容服务流响应不符合 {label} 格式。') from error
    return ProviderCompletion(text=text, provider='openai-compatible', model=payload['model'],
        latency_ms=round((time.monotonic() - started) * 1000), usage=usage,
        structured=_structured(text, schema))
