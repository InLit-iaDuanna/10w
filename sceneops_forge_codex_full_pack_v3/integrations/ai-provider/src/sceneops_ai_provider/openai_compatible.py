"""OpenAI-compatible Chat Completions and Responses transports."""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import httpx

from .service import (
    ApiProtocol,
    ProviderCompletion,
    ProviderFailure,
    ProviderModel,
    SYSTEM_PROMPT,
    _safe_usage,
)


def _image_url(path: Path) -> str:
    media_type = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
    }[path.suffix.casefold()]
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return f'data:{media_type};base64,{encoded}'


def _chat_payload(prompt: str, model: str, schema: dict | None,
                  image_paths: list[Path]) -> dict[str, Any]:
    user_content: str | list[dict[str, Any]] = prompt
    if image_paths:
        user_content = [{'type': 'text', 'text': prompt}]
        user_content.extend({'type': 'image_url', 'image_url': {'url': _image_url(path)}}
                            for path in image_paths)
    payload: dict[str, Any] = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_content},
        ],
    }
    if schema is not None:
        payload['response_format'] = {
            'type': 'json_schema',
            'json_schema': {'name': 'sceneops_response', 'strict': False, 'schema': schema},
        }
    return payload


def _responses_payload(prompt: str, model: str, schema: dict | None,
                       image_paths: list[Path]) -> dict[str, Any]:
    input_value: str | list[dict[str, Any]] = prompt
    if image_paths:
        content: list[dict[str, Any]] = [{'type': 'input_text', 'text': prompt}]
        content.extend({'type': 'input_image', 'image_url': _image_url(path)}
                       for path in image_paths)
        input_value = [{'role': 'user', 'content': content}]
    payload: dict[str, Any] = {
        'model': model,
        'instructions': SYSTEM_PROMPT,
        'input': input_value,
        'store': False,
    }
    if schema is not None:
        payload['text'] = {'format': {
            'type': 'json_schema',
            'name': 'sceneops_response',
            'strict': False,
            'schema': schema,
        }}
    return payload


def build_payload(api_protocol: ApiProtocol, prompt: str, model: str,
                  schema: dict | None, image_paths: list[Path]) -> dict[str, Any]:
    if api_protocol == 'responses':
        return _responses_payload(prompt, model, schema, image_paths)
    return _chat_payload(prompt, model, schema, image_paths)


def _raise_for_status(response: httpx.Response, api_protocol: ApiProtocol | None = None) -> None:
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


def _chat_text(envelope: object) -> str:
    try:
        content = envelope['choices'][0]['message']['content']  # type: ignore[index]
    except (KeyError, IndexError, TypeError) as error:
        raise ProviderFailure('OPENAI_INVALID_RESPONSE',
                              '兼容服务响应不符合 Chat Completions 格式。') from error
    if not isinstance(content, str) or not content.strip():
        raise ProviderFailure('OPENAI_INVALID_RESPONSE', '兼容服务未返回有效文字回复。')
    return content


def _responses_text(envelope: object) -> str:
    if not isinstance(envelope, dict) or envelope.get('status') != 'completed':
        raise ProviderFailure('OPENAI_INVALID_RESPONSE', '兼容服务没有返回已完成的 Response。')
    output = envelope.get('output')
    if not isinstance(output, list):
        raise ProviderFailure('OPENAI_INVALID_RESPONSE', '兼容服务响应不符合 Responses API 格式。')
    text: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get('type') != 'message':
            continue
        content = item.get('content')
        if not isinstance(content, list):
            continue
        text.extend(part['text'] for part in content
                    if isinstance(part, dict) and part.get('type') == 'output_text'
                    and isinstance(part.get('text'), str))
    value = ''.join(text)
    if not value.strip():
        raise ProviderFailure('OPENAI_INVALID_RESPONSE', '兼容服务未返回有效文字回复。')
    return value


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


async def generate_completion(*, base_url: str, api_key: str, api_protocol: ApiProtocol,
                              prompt: str, model: str, schema: dict | None,
                              image_paths: list[Path], timeout: float,
                              on_event=None) -> ProviderCompletion:
    endpoint = base_url + ('/responses' if api_protocol == 'responses' else '/chat/completions')
    payload = build_payload(api_protocol, prompt, model, schema, image_paths)
    started = time.monotonic()
    if on_event is not None:
        from .openai_stream import stream_completion
        return await stream_completion(endpoint=endpoint, api_key=api_key,
            api_protocol=api_protocol, payload=payload, timeout=timeout,
            started=started, schema=schema, on_event=on_event)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                    trust_env=False) as client:
            response = await client.post(endpoint, headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }, json=payload)
    except httpx.TimeoutException as error:
        raise ProviderFailure('OPENAI_TIMEOUT',
                              'OpenAI 兼容服务请求超时，请检查服务状态后重试。') from error
    except httpx.RequestError as error:
        raise ProviderFailure('OPENAI_NETWORK_ERROR',
                              '无法连接 OpenAI 兼容服务，请检查地址、网络或本机服务。') from error
    _raise_for_status(response, api_protocol)
    try:
        envelope = response.json()
    except ValueError as error:
        raise ProviderFailure('OPENAI_INVALID_RESPONSE', '兼容服务没有返回有效 JSON。') from error
    text = _responses_text(envelope) if api_protocol == 'responses' else _chat_text(envelope)
    usage = _safe_usage(envelope.get('usage')) if isinstance(envelope, dict) else None
    return ProviderCompletion(text=text, provider='openai-compatible', model=model,
        latency_ms=round((time.monotonic() - started) * 1000), usage=usage,
        structured=_structured(text, schema))


async def list_models(*, base_url: str, api_key: str, timeout: float) -> list[ProviderModel]:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                    trust_env=False) as client:
            response = await client.get(base_url + '/models', headers={
                'Authorization': f'Bearer {api_key}',
                'Accept': 'application/json',
            })
    except httpx.TimeoutException as error:
        raise ProviderFailure('OPENAI_TIMEOUT',
                              '获取模型列表超时，请检查兼容服务状态后重试。') from error
    except httpx.RequestError as error:
        raise ProviderFailure('OPENAI_NETWORK_ERROR',
                              '无法连接兼容服务获取模型，请检查地址与网络。') from error
    _raise_for_status(response)
    try:
        data = response.json()['data']
    except (ValueError, KeyError, TypeError) as error:
        raise ProviderFailure('OPENAI_MODELS_INVALID',
                              '兼容服务的模型列表不符合 OpenAI 格式。') from error
    if not isinstance(data, list):
        raise ProviderFailure('OPENAI_MODELS_INVALID', '兼容服务的模型列表不是数组。')
    identifiers = {
        item['id'].strip() for item in data
        if isinstance(item, dict) and isinstance(item.get('id'), str)
        and 0 < len(item['id'].strip()) <= 200
        and not any(character in item['id'] for character in '\r\n\x00')
    }
    if not identifiers:
        raise ProviderFailure('OPENAI_MODELS_EMPTY', '兼容服务没有返回可用模型。')
    return [ProviderModel(identifier, identifier, 'openai-compatible')
            for identifier in sorted(identifiers, key=str.casefold)]
