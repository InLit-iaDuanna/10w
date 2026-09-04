from __future__ import annotations

import asyncio

import httpx
from fastapi import FastAPI

from concept_lab.errors import ConceptLabError
from concept_lab.router import concept_lab_error_handler, create_router


def _app(service):
    app = FastAPI()
    app.add_exception_handler(ConceptLabError, concept_lab_error_handler)
    app.include_router(create_router(service))
    return app


def _request(service, method, path, json=None):
    async def send():
        transport = httpx.ASGITransport(app=_app(service))
        async with httpx.AsyncClient(
            transport=transport, base_url="http://concept-lab.test"
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_create_and_get_concept_api(service, hero_request):
    response = _request(
        service,
        "POST",
        "/v1/concepts",
        json={
            "command": {
                "actor_id": "usr_designer",
                "correlation_id": "corr_api",
                "causation_id": "cmd_api_create",
            },
            "concept": hero_request.model_dump(mode="json"),
        },
    )
    assert response.status_code == 201
    concept = response.json()
    assert concept["subject"] == "旧宅正门黄铜钥匙"
    loaded = _request(service, "GET", f"/v1/concepts/{concept['concept_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["project_bible_version_id"] == "pbv_remember_home_003"
    workspace = _request(
        service, "GET", f"/v1/concepts/{concept['concept_id']}/review-workspace"
    )
    assert workspace.status_code == 200
    assert workspace.json()["concept"]["concept_id"] == concept["concept_id"]
    assert workspace.json()["variants"] == []


def test_api_exposes_structured_failure_state(service):
    response = _request(service, "GET", "/v1/concepts/cpt_missing")
    assert response.status_code == 404
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "concept was not found.",
        "details": {"entity": "concept", "id": "cpt_missing"},
        "request_id": None,
        "retryable": False,
        "suggested_actions": [],
    }
