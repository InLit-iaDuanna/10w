"""Composition hook for a queue worker; domain execution stays in AIPlaytestService."""

from ai_playtest import AIPlaytestService, RunRequest


def execute_playtest(service: AIPlaytestService, payload: dict):
    return service.run(RunRequest.model_validate(payload))
