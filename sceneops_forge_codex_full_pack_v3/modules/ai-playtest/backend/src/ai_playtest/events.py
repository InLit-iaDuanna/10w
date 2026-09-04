from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .schemas import (
    Backpin,
    BackpinStatus,
    ExecutionMode,
    Issue,
    PlaytestStep,
    RegressionComparison,
    RunId,
    StableId,
    StrictModel,
    UtcDatetime,
)


class EventActor(StrictModel):
    type: Literal["user", "agent", "system"]
    id: StableId


class EventFields(StrictModel):
    event_id: StableId
    event_version: Literal[1] = 1
    occurred_at: UtcDatetime
    project_id: StableId
    correlation_id: StableId
    causation_id: StableId
    actor: EventActor
    mode: ExecutionMode


class PlaytestRunStartedPayload(StrictModel):
    run_id: RunId
    test_case_id: StableId
    build_id: StableId
    execution_mode: ExecutionMode


class PlaytestRunStartedEvent(EventFields):
    event_type: Literal["playtest.run.started"] = "playtest.run.started"
    payload: PlaytestRunStartedPayload

    @model_validator(mode="after")
    def validate_mode(self) -> "PlaytestRunStartedEvent":
        if self.mode != self.payload.execution_mode:
            raise ValueError("event mode must match run payload mode")
        return self


class PlaytestStepRecordedEvent(EventFields):
    event_type: Literal["playtest.step.recorded"] = "playtest.step.recorded"
    payload: PlaytestStep

    @model_validator(mode="after")
    def validate_mode(self) -> "PlaytestStepRecordedEvent":
        if self.mode != self.payload.evidence.execution_mode:
            raise ValueError("event mode must match step evidence mode")
        return self


class PlaytestIssueCreatedEvent(EventFields):
    event_type: Literal["playtest.issue.created"] = "playtest.issue.created"
    payload: Issue

    @model_validator(mode="after")
    def validate_mode(self) -> "PlaytestIssueCreatedEvent":
        if self.mode != self.payload.execution_mode:
            raise ValueError("event mode must match issue mode")
        return self


class PlaytestIssueBackpinResolvedPayload(StrictModel):
    issue_id: StableId
    backpin: Backpin
    execution_mode: ExecutionMode


class PlaytestIssueBackpinResolvedEvent(EventFields):
    event_type: Literal["playtest.issue.backpin.resolved"] = (
        "playtest.issue.backpin.resolved"
    )
    payload: PlaytestIssueBackpinResolvedPayload

    @model_validator(mode="after")
    def validate_mode(self) -> "PlaytestIssueBackpinResolvedEvent":
        if self.mode != self.payload.execution_mode:
            raise ValueError("event mode must match backpin payload mode")
        if self.payload.backpin.status != BackpinStatus.RESOLVED:
            raise ValueError("backpin resolved events require resolved status")
        return self


class PlaytestRegressionComparedEvent(EventFields):
    event_type: Literal["playtest.regression.compared"] = (
        "playtest.regression.compared"
    )
    payload: RegressionComparison

    @model_validator(mode="after")
    def validate_mode(self) -> "PlaytestRegressionComparedEvent":
        if self.mode != self.payload.execution_mode:
            raise ValueError("event mode must match regression mode")
        return self


EVENT_MODELS = {
    "playtest.run.started": PlaytestRunStartedEvent,
    "playtest.step.recorded": PlaytestStepRecordedEvent,
    "playtest.issue.created": PlaytestIssueCreatedEvent,
    "playtest.issue.backpin.resolved": PlaytestIssueBackpinResolvedEvent,
    "playtest.regression.compared": PlaytestRegressionComparedEvent,
}
