"""Isolated, mock-only workbench orchestration through public module services."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4
from threading import RLock
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from concept_lab import (ConceptLabService, ConceptCreateInput, FixtureGenerationAdapter,
    ExecutionMode as ConceptMode, GenerationRequest, ReviewAction, StyleEvidenceInput,
    ConceptReviewWorkspace)
from asset_library import (AssetLibraryService, InMemoryAssetRepository, AssetRecord,
    SourceAsset, AssetObjectIdentity, AssetSearchFilter)
from sceneops_blender import DeterministicMockBlenderAdapter
from .concept_handoff import ConceptAssetHandoff, asset_spec_from_concept
from .schemas import PipelineRequest, AssetChangeSet, PipelineRun
from .authorization import (AssetApprovalRecord, InMemoryAssetApprovalAuthority,
    InMemoryProjectRootRegistry, ProjectArtifactVerifier, canonical_command_scope)
from .finalization import InMemoryFinalizedCandidateStore
from .run_ledger import InMemoryRequestLedger
from .service import AssetPipelineService
from .workflow import build_workflow_plan

class LabAction(BaseModel):
    action: Literal["generate", "evidence", "comment", "approve", "reject", "compile", "preview", "produce"]
    variant_id: str = ""
    note: str = Field(default="", max_length=4000)

class LabSnapshot(BaseModel):
    mode: Literal["mock"] = "mock"
    workspace: ConceptReviewWorkspace | None = None
    handoff: ConceptAssetHandoff | None = None
    request: PipelineRequest | None = None
    runs: list[PipelineRun]
    assets: list[AssetRecord]

class ConceptAssetLab:
    def __init__(self, root: Path, *, seed: bool = True, project_id: str | None = None):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        import concept_lab
        fixtures = Path(concept_lab.__file__).parent / "fixtures"
        self.concepts = ConceptLabService(adapters=[FixtureGenerationAdapter(
            fixtures / "generation-mock.json", ConceptMode.MOCK)])
        self.context = dict(actor_id="usr_local_artist", correlation_id="corr_lab", causation_id="cmd_lab")
        self.project_id = project_id
        self.concept = None
        if seed:
            self.import_sample("remember-home")
        self.repository = InMemoryAssetRepository()
        self.catalog = AssetLibraryService(self.repository)
        self.handoff = None
        self.request = None
        self.runs = []
        self.lock = RLock()

    def snapshot(self):
        return LabSnapshot(workspace=self.concepts.get_review_workspace(self.concept.concept_id, 1) if self.concept else None,
            handoff=self.handoff, request=self.request, runs=self.runs,
            assets=self.catalog.search(AssetSearchFilter()))

    def import_sample(self, sample_id: str):
        if self.concept is not None:
            raise ValueError("已有概念数据；请在新的项目中导入样例。")
        import concept_lab
        payload = json.loads((Path(concept_lab.__file__).parent / "fixtures/hero-key-concept.json").read_text())
        if self.project_id:
            payload["project_id"] = self.project_id
        if sample_id == "warehouse-escape":
            payload.update(subject="仓库出口黄铜钥匙", gameplay_function="拾取后开启仓库出口",
                feature_id="fea_warehouse_exit", task_id="tsk_warehouse_key_concept")
        self.concept = self.concepts.create_concept(ConceptCreateInput.model_validate(payload), **self.context)

    def act(self, action: LabAction):
        with self.lock:
            if self.concept is None:
                raise ValueError("请先明确导入概念样例；不会自动创建演示项目。")
            cid, vid = self.concept.concept_id, action.variant_id
            if action.action == "generate":
                self.concepts.generate_variant(GenerationRequest(concept_id=cid, concept_version=1,
                    title="黄铜钥匙 · Mock 参考方案", requested_views=["front", "three_quarter"],
                    prompt="Aged hand-forged brass house key", negative_prompt="electronic fob",
                    seed=240906, workflow_version="concept-multiview-fixture@1", execution_mode="mock",
                    adapter_id="concept-fixture-mock", model="fixture-key-v1", fixture_key="hero-key-v1"), **self.context)
            elif action.action == "comment":
                self.concepts.comment_on_variant(cid, vid, action.note, "usr_local_artist")
            elif action.action == "evidence":
                workspace = self.snapshot().workspace
                variant = next(v for v in workspace.variants if v.variant_id == vid)
                evidence = [StyleEvidenceInput(criterion=c, criterion_kind=k, observed=action.note,
                    verdict="match", evidence_reference_id=variant.reference_ids[0], confidence=0.7,
                    rationale="人工声明的 mock 参考评审；不是像素分析或客观艺术评分")
                    for k, values in [("style_constraint", self.concept.style_constraints),
                                      ("forbidden_element", self.concept.forbidden_elements)] for c in values]
                self.concepts.add_style_check(cid, 1, vid, evidence, created_by="usr_local_artist")
            elif action.action in ("approve", "reject"):
                self.concepts.review_variant(cid, 1, vid, ReviewAction(action.action),
                    rationale=action.note, reviewer_id="usr_local_artist", acknowledge_license_warning=False,
                    correlation_id="corr_lab", causation_id="cmd_review")
            elif action.action == "compile":
                if self.request:
                    raise ValueError("本隔离会话已有生产规格；重启可开始新一轮。")
                draft = self.concepts.compile_asset_spec_draft(cid, 1, vid, **self.context)
                self.handoff = asset_spec_from_concept(draft, asset_id="ast_" + uuid4().hex)
                self._prepare()
            elif action.action in ("preview", "produce"):
                self._run(action.action == "preview")
            return self.snapshot()

    def _prepare(self):
        spec = self.handoff.spec
        source = SourceAsset(source_asset_id="src_" + spec.asset_id, asset_id=spec.asset_id,
            project_id=spec.project_id, project_relative_path="Assets/key.mock.blend", format="blend",
            source_version="1", source_kind="generated", license_name="CC0-1.0",
            origin_uri="fixture://concept-assets/key", imported_at=datetime.now(timezone.utc))
        path = self.root / source.project_relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("MOCK ONLY: not a Blender document")
        identity = AssetObjectIdentity(sceneops_id="sop_" + spec.asset_id,
            source_asset_id=source.source_asset_id, display_name=spec.display_name, source_object_locator="Key")
        self.catalog.register(AssetRecord(spec=spec, source=source, source_objects=[identity]))
        change = AssetChangeSet(change_set_id="chg_" + spec.asset_id, base_version="source:1",
            project_id=spec.project_id, target_object_ids=[identity.sceneops_id],
            previous_values={"source": source.project_relative_path}, proposed_values={"formats": ["glb", "fbx"], "mode": "mock"},
            rationale="将已批准概念制作成隔离 mock 资产", expected_result="Mock 资产版本与检查记录",
            impact_scope=[spec.asset_id], risk="medium", validation_plan=["geometry", "uv_material", "identity"],
            rollback_plan=["restore Blender snapshot"], approval_requirements=["asset owner"])
        self.request = PipelineRequest(pipeline_run_id="run_" + uuid4().hex, idempotency_key=uuid4().hex,
            spec=spec, source=source, source_object_identities=[identity], asset_version_id="aver_" + spec.asset_id,
            asset_version_number=1, output_directory="Published/" + spec.asset_id, change_set=change,
            requested_mode="mock", dry_run=False, creator="usr_local_artist")

    def _run(self, preview):
        if not self.request:
            raise ValueError("请先批准概念并编译资产规格。")
        if any(r.state.value == "succeeded" for r in self.runs):
            raise ValueError("本规格已完成，资产库中可检查结果。")
        request = self.request.model_copy(deep=True)
        request.pipeline_run_id = "run_" + uuid4().hex
        request.idempotency_key = uuid4().hex
        request.dry_run = preview
        approvals = []
        if not preview:
            change = request.change_set
            change.state = "approved"
            change.approval_id = "apr_" + uuid4().hex
            change.approved_by = "usr_local_artist"
            change.approved_at = datetime.now(timezone.utc)
            # Revalidate enum values after assignment before the trusted authority consumes it.
            request = PipelineRequest.model_validate(request.model_dump())
            change = request.change_set
            approvals = [AssetApprovalRecord(approval_id=change.approval_id, change_set_id=change.change_set_id,
                project_id=change.project_id, asset_id=request.spec.asset_id, asset_version_id=request.asset_version_id,
                approved_by=change.approved_by, approved_at=change.approved_at, change_set=change,
                command_scope=canonical_command_scope((c for p in build_workflow_plan(request, preview=False)
                    for c in p.commands), request.pipeline_run_id))]
        authority = InMemoryAssetApprovalAuthority(approvals)
        roots = InMemoryProjectRootRegistry({request.spec.project_id: self.root})
        candidates = InMemoryFinalizedCandidateStore()
        self.catalog = AssetLibraryService(self.repository, approval_verifier=authority,
            artifact_verifier=ProjectArtifactVerifier(roots), candidate_resolver=candidates)
        pipeline = AssetPipelineService(self.catalog, authority, roots, candidates, InMemoryRequestLedger())
        self.runs.append(pipeline.run(request, DeterministicMockBlenderAdapter(self.root)))

def create_lab_router(lab: ConceptAssetLab):
    router = APIRouter(prefix="/api")
    @router.get("/workspace", response_model=LabSnapshot)
    def workspace():
        with lab.lock:
            return lab.snapshot()
    @router.post("/actions", response_model=LabSnapshot)
    def action(body: LabAction):
        try:
            return lab.act(body)
        except (ValueError, LookupError, StopIteration) as error:
            raise HTTPException(409, detail=str(error) or "未找到所选方案") from error
    return router
