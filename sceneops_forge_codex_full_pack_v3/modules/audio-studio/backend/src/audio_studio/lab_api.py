"""Session-local audio inspection and non-executing binding proposals."""
from __future__ import annotations

import base64
import binascii
import json
import struct
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .models import AudioAnalysis, ChangeSet, ChangeSetStatus
from .service import AudioStudioService, hero_audio_template, warehouse_escape_template


class Event(BaseModel):
    name: str
    target: str
    mixer: str


class Project(BaseModel):
    id: Literal["home", "warehouse"]
    title: str
    events: list[Event]


class Upload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=200)
    data: str = Field(max_length=5_600_000)


class Inspection(BaseModel):
    id: str
    filename: str
    analysis: AudioAnalysis
    mode: Literal["live", "mock"]
    provenance_status: str = "仅会话内分析，未发布资产；无生成来源声明。"


class BindingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template: Literal["home", "warehouse"]
    event: str
    asset_id: str
    mixer: str = Field(min_length=1, max_length=100)


class Proposal(BaseModel):
    id: str
    title: str
    status: str
    details: str
    approved_at: str | None = None
    mode: Literal["planned"] = "planned"


class DemoAudio(BaseModel):
    filename: str
    data: str
    mode: Literal["mock"] = "mock"


def mock_key_pickup_wav() -> bytes:
    """Existing deterministic test signal, promoted to a public demo fixture."""
    rate = 8000
    samples = [16384 if index % 2 == 0 else -16384 for index in range(rate)]
    pcm = struct.pack("<" + "h" * len(samples), *samples)
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
            + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(pcm)) + pcm)


def create_lab_router() -> APIRouter:
    router = APIRouter(prefix="/api/audio", tags=["Audio Studio"])
    service = AudioStudioService(module_enabled=True, unity_online=False)
    assets: dict[tuple[UUID, str], Inspection] = {}
    changes: dict[tuple[UUID, str], ChangeSet] = {}

    def inspect(data: bytes, filename: str, session: UUID, mode: str) -> Inspection:
        result = Inspection(id="audio_" + uuid4().hex, filename=filename,
                            analysis=service.inspect_wav(data, filename), mode=mode)
        assets[(session, result.id)] = result
        return result

    def view(change: ChangeSet) -> Proposal:
        payload = {key: value for key, value in asdict(change).items() if not key.startswith("_")}
        return Proposal(id=change.change_set_id, title="音频事件绑定", status=change.status.value,
                        details=json.dumps(payload, ensure_ascii=False, indent=2), approved_at=change.approved_at)

    @router.get("/projects", response_model=list[Project])
    def projects():
        return [Project(id=key, title=title, events=[Event(name=e, target=t, mixer=m) for e, t, m in loader()])
                for key, title, loader in (("home", "寻找回家的路", hero_audio_template),
                                           ("warehouse", "仓库逃生", warehouse_escape_template))]

    @router.get("/fixture", response_model=DemoAudio)
    def fixture():
        return DemoAudio(filename="mock-key-pickup.wav", data=base64.b64encode(mock_key_pickup_wav()).decode())

    @router.post("/inspect-fixture", response_model=Inspection)
    def inspect_fixture(session: UUID = Header(alias="X-Lab-Session")):
        return inspect(mock_key_pickup_wav(), "mock-key-pickup.wav", session, "mock")

    @router.post("/inspect", response_model=Inspection)
    def inspect_upload(upload: Upload, session: UUID = Header(alias="X-Lab-Session")):
        try:
            data = base64.b64decode(upload.data, validate=True)
        except (ValueError, binascii.Error) as error:
            raise HTTPException(422, "音频编码无效，请重新选择文件。") from error
        return inspect(data, upload.filename, session, "live")

    @router.get("/proposals", response_model=list[Proposal])
    def proposals(session: UUID = Header(alias="X-Lab-Session")):
        return [view(value) for (owner, _), value in changes.items() if owner == session]

    @router.post("/proposals", response_model=Proposal)
    def propose(draft: BindingDraft, session: UUID = Header(alias="X-Lab-Session")):
        asset = assets.get((session, draft.asset_id))
        if asset is None:
            raise HTTPException(404, "分析结果已失效，请重新分析音频。")
        events = hero_audio_template() if draft.template == "home" else warehouse_escape_template()
        targets = {name: target for name, target, _ in events}
        if draft.event not in targets:
            raise HTTPException(422, "事件不属于当前演示项目。")
        binding = service.bind_event(draft.event, draft.asset_id)
        identity = "chg_" + uuid4().hex
        change = ChangeSet(identity, ChangeSetStatus.DRAFT, "demo-1", "unity", (targets[draft.event],),
            {"AudioSource.clip": None, "Mixer": None},
            {"AudioSource.clip": binding.audio_asset_id, "AudioSource.name": "InteractionAudio",
             "Mixer": draft.mixer, "event": draft.event, "source": asset.filename,
             "asset_state": "unpublished-session-inspection"},
            "补充可选交互音效", "事件触发一次音频", "当前事件与 AudioSource", "音频尚未发布",
            "发布资产后连接 Unity 验证音量与路由", "恢复 previous_values", ("本地人工审阅；非生产授权",), ())
        service.submit_changeset(change)
        changes[(session, identity)] = change
        return view(change)

    @router.post("/proposals/{identity}/approve", response_model=Proposal)
    def approve(identity: str, session: UUID = Header(alias="X-Lab-Session")):
        change = changes.get((session, identity))
        if change is None:
            raise HTTPException(404, "提案不存在或会话已重启，请重新创建。")
        if change.status is not ChangeSetStatus.SUBMITTED:
            raise HTTPException(409, "此提案已经审阅。")
        service.approve_changeset(change, approver_id="local-reviewer",
            approved_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            approval_evidence=("用户点击本地批准；不授权 Unity 发布",))
        return view(change)

    return router
