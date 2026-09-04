"""Stable identifier types shared by SceneOps Forge modules."""

from typing import Annotated, Dict

from pydantic import StringConstraints


_SUFFIX = r"[A-Za-z0-9][A-Za-z0-9_-]{7,127}"


def _stable_id(prefix: str):
    return Annotated[str, StringConstraints(pattern=rf"^{prefix}_{_SUFFIX}$")]


StableId = Annotated[
    str,
    StringConstraints(
        pattern=rf"^(?:usr|agt|svc|sys|prj|brn|scn|sobj|ast|aver|bld|run|iss|chg|apr|art|evt|cmd|corr|req|wfl|fea|tsk|rjob|prun)_{_SUFFIX}$"
    ),
]
ActorId = Annotated[
    str,
    StringConstraints(pattern=rf"^(?:usr|agt|svc|sys)_{_SUFFIX}$"),
]
UserId = _stable_id("usr")
AgentId = _stable_id("agt")
ServiceId = _stable_id("svc")
SystemActorId = _stable_id("sys")
ProjectId = _stable_id("prj")
BranchId = _stable_id("brn")
SceneId = _stable_id("scn")
SceneObjectId = _stable_id("sobj")
AssetId = _stable_id("ast")
AssetVersionId = _stable_id("aver")
BuildId = _stable_id("bld")
RunId = _stable_id("run")
IssueId = _stable_id("iss")
ChangeSetId = _stable_id("chg")
ApprovalId = _stable_id("apr")
ArtifactId = _stable_id("art")
EventId = _stable_id("evt")
CommandId = _stable_id("cmd")
CorrelationId = _stable_id("corr")
RequestId = _stable_id("req")
WorkflowId = _stable_id("wfl")
FeatureId = _stable_id("fea")
TaskId = _stable_id("tsk")
RenderJobId = _stable_id("rjob")
PlaytestRunId = _stable_id("prun")

ModuleId = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
]
ContributionId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$"),
]
Sha256Checksum = Annotated[
    str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")
]


ID_PATTERNS: Dict[str, str] = {
    "StableId": rf"^(?:usr|agt|svc|sys|prj|brn|scn|sobj|ast|aver|bld|run|iss|chg|apr|art|evt|cmd|corr|req|wfl|fea|tsk|rjob|prun)_{_SUFFIX}$",
    "ActorId": rf"^(?:usr|agt|svc|sys)_{_SUFFIX}$",
    "UserId": rf"^usr_{_SUFFIX}$",
    "AgentId": rf"^agt_{_SUFFIX}$",
    "ServiceId": rf"^svc_{_SUFFIX}$",
    "SystemActorId": rf"^sys_{_SUFFIX}$",
    "ProjectId": rf"^prj_{_SUFFIX}$",
    "BranchId": rf"^brn_{_SUFFIX}$",
    "SceneId": rf"^scn_{_SUFFIX}$",
    "SceneObjectId": rf"^sobj_{_SUFFIX}$",
    "AssetId": rf"^ast_{_SUFFIX}$",
    "AssetVersionId": rf"^aver_{_SUFFIX}$",
    "BuildId": rf"^bld_{_SUFFIX}$",
    "RunId": rf"^run_{_SUFFIX}$",
    "IssueId": rf"^iss_{_SUFFIX}$",
    "ChangeSetId": rf"^chg_{_SUFFIX}$",
    "ApprovalId": rf"^apr_{_SUFFIX}$",
    "ArtifactId": rf"^art_{_SUFFIX}$",
    "EventId": rf"^evt_{_SUFFIX}$",
    "CommandId": rf"^cmd_{_SUFFIX}$",
    "CorrelationId": rf"^corr_{_SUFFIX}$",
    "RequestId": rf"^req_{_SUFFIX}$",
    "WorkflowId": rf"^wfl_{_SUFFIX}$",
    "FeatureId": rf"^fea_{_SUFFIX}$",
    "TaskId": rf"^tsk_{_SUFFIX}$",
    "RenderJobId": rf"^rjob_{_SUFFIX}$",
    "PlaytestRunId": rf"^prun_{_SUFFIX}$",
    "ModuleId": r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$",
    "ContributionId": r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$",
    "Sha256Checksum": r"^sha256:[0-9a-f]{64}$",
}


__all__ = list(ID_PATTERNS)
