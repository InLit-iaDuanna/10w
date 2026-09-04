"""Local proposal/read surface. Never configures an external runner."""
import json
from pathlib import Path
from uuid import uuid4
from .adapter import UnityAdapter
from .service import UnityEngineService
from .errors import UnityIntegrationError
from .contracts import ChangeSet, CommandRequest, ExecutionContext, CapabilityReport, ChangePreview
from pydantic import BaseModel

class UnityWorkbenchSnapshot(BaseModel):
    mode: str = "mock"
    connection_mode: str = "blocked"
    connection_reason: str = "本工作台未连接 Unity；所有外部执行均未启用。"
    capabilities: CapabilityReport
    objects: list[dict]
    commands: list[dict]

class UnityProposalPreview(BaseModel):
    change_set: ChangeSet
    preview: ChangePreview

class UnityWorkbenchService:
    def __init__(self):
        self.root = Path(__file__).resolve().parents[3]
        self.adapter = UnityAdapter.with_defaults(unity_editor=None, fixture_file=self.root / "fixtures/mock/command-results.json")
        self.service = UnityEngineService(self.adapter)

    def snapshot(self):
        fixture = json.loads((self.root / "fixtures/mock/command-results.json").read_text())
        inspected = fixture["commands"]["unity.game_object.inspect"]["data"]
        return UnityWorkbenchSnapshot(capabilities=self.adapter.capabilities(), objects=[inspected], commands=[
            {"command": name, "mode": "mock", **record} for name, record in fixture["commands"].items()
        ])

    def preview(self, change_set: ChangeSet):
        if change_set.approval_state.value != "pending":
            raise ValueError("本地提案必须保持 pending；审批由可信审批系统提供。")
        root = str(self.root / "fixtures/unity-projects/smoke-template")
        request = CommandRequest(request_id="req_" + uuid4().hex, idempotency_key=uuid4().hex,
            command=change_set.command, project_id="prj_lab_mock", project_root=root,
            base_version="lab-mock-v1", mode="planned", payload=change_set.proposed_values, change_set=change_set)
        context = ExecutionContext(configured_project_roots=[root], permissions={"unity:read", "unity:write", "unity:build", "unity:execute"},
            current_base_version="lab-mock-v1", actor_id="local-proposal-author")
        try:
            preview = self.service.preview(request, context)
        except UnityIntegrationError as error:
            raise ValueError(f"{error.code.value}: {error}") from error
        return UnityProposalPreview(change_set=change_set, preview=preview)
