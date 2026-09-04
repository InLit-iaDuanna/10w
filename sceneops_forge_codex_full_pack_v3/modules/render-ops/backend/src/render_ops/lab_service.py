"""Local workbench orchestration over the existing Render Ops services."""

from datetime import datetime, timezone
from uuid import uuid4

from .fixtures import mock_manifest, mock_dependency_snapshot, mock_artifact
from .jobs import RenderJobRepository, RenderQueue
from .lab_contracts import (
    LabState, LabJob, LabRecipeInput, LabProposalInput, LabCompareInput, LabComparison,
)
from .lab_fixtures import sample_images, door_mask
from .recipes import load_recipe_catalog
from .schemas import (
    AovArtifact, AovPass, ArtifactApprovalState, ExecutionMode, RenderBrief,
    RenderRecipe, RenderJobState, WritebackOperation, WritebackProperty, WritebackTarget,
)
from .service import RenderOpsService
from .validation import compare_protected_region, make_comparison
from .writeback import approve_writeback


class RenderLabService:
    """One instance per browser session; state lasts until API restart/reset."""

    def __init__(self, *, seed: bool = True, project_id: str | None = None):
        self.domain = RenderOpsService()
        self.fixture = mock_manifest()
        if project_id:
            scene = self.fixture.brief.scene.model_copy(update={"project_id": project_id})
            brief = self.fixture.brief.model_copy(update={"scene": scene})
            self.fixture = self.fixture.model_copy(update={"brief": brief})
        self.repository = RenderJobRepository()
        self.queue = RenderQueue(self.repository)
        self.records = []
        self.activity = []
        if seed:
            initial = LabRecipeInput(
                recipe_id="render.lighting-visibility", prompt="让门廊钥匙区域更清晰，保留门体轮廓。"
            )
            record = self.plan(initial)
            self.load_fixture(record.job.job_id)

    def snapshot(self):
        for record in self.records:
            record.job = self.repository.get(record.job.job_id)
        return LabState(
            brief=self.fixture.brief, recipes=load_recipe_catalog().recipes,
            jobs=self.records, activity=self.activity[-30:],
        )

    def record(self, job_id):
        for record in self.records:
            if record.job.job_id == job_id:
                record.job = self.repository.get(job_id)
                return record
        raise KeyError("找不到所选任务，请刷新工作台。")

    def plan(self, request: LabRecipeInput):
        definition = next((item for item in load_recipe_catalog().recipes
                           if item.recipe_id == request.recipe_id), None)
        if definition is None:
            raise ValueError("未知配方，请从配方目录选择。")
        scene = self.fixture.brief.scene.model_copy(update={"camera_version": request.camera_version})
        brief = RenderBrief.model_validate({**self.fixture.brief.model_dump(), "scene": scene})
        recipe = RenderRecipe(
            recipe_id=definition.recipe_id, version=definition.version, kind=definition.kind,
            required_passes=definition.required_passes, optional_passes=definition.optional_passes,
            workflow_reference=self.fixture.recipe.workflow_reference,
            workflow_checksum_sha256=self.fixture.recipe.workflow_checksum_sha256,
            parameters={"samples": request.samples, "resolution": [16, 16]},
        )
        previous = next((item for item in reversed(self.records) if item.aovs), None)
        snapshot = mock_dependency_snapshot(
            recipe_id=recipe.recipe_id, recipe_version=recipe.version,
            samples=request.samples, geometry_version=request.geometry_version,
            camera_version=request.camera_version, width=16, height=16,
        )
        job = self.domain.create_job(
            job_id="lab-job-" + uuid4().hex[:12], brief=brief, recipe=recipe,
            dependency_snapshot=snapshot,
            existing_aovs={item.pass_type: item for item in previous.aovs} if previous else {},
            previous_snapshot=previous.job.dependency_snapshot if previous else None,
            execution_mode=ExecutionMode.MOCK,
        )
        self.queue.enqueue(job)
        record = LabJob(job=job, recipe=recipe, input=request)
        self.records.append(record)
        self.activity.append(f"已规划 {job.job_id}：复用 {len(job.cache_plan.reused_passes)} 个 mock AOV。")
        return record

    def load_fixture(self, job_id):
        record = self.record(job_id)
        if record.job.state != RenderJobState.QUEUED:
            raise ValueError("只有排队中的任务可以载入样本。")
        job = self.queue.start(job_id)
        aovs = []
        for pass_type in record.recipe.required_passes:
            artifact = mock_artifact(f"{job_id}-{pass_type.value}", "render.aov")
            aovs.append(AovArtifact(
                pass_type=pass_type, scene=job.scene, width=16, height=16, artifact=artifact,
            ))
        self.domain.validate_capture(job=job, recipe=record.recipe, aovs=aovs)
        record.aovs = aovs
        record.images = sample_images()
        record.variants = []
        for name, seed_offset in (("warm", 0), ("bright", 1)):
            provenance = self.fixture.variants[0].provenance.model_copy(update={
                "provider": "deterministic-local-fixture",
                "prompt": record.input.prompt, "negative_prompt": record.input.negative_prompt,
                "seed": record.input.seed + seed_offset,
                "parameters": {"sample": name, "requested_samples": record.input.samples,
                               "requested_ai_provider": record.input.ai_provider,
                               "requested_ai_model": record.input.ai_model,
                               "ai_invoked": False,
                               "image_changes_with_prompt": False},
            })
            output = mock_artifact(f"{job_id}-{name}", "render.variant", ArtifactApprovalState.PENDING)
            variant = self.domain.create_variant(
                variant_id=f"{job_id}-{name}", job=job, recipe=record.recipe,
                output=output, provenance=provenance,
                constraint_passes=[AovPass.DEPTH, AovPass.NORMAL, AovPass.OBJECT_ID],
            )
            record.variants.append(variant)
            record.images[variant.variant_id] = record.images[name]
        record.job = self.queue.wait_for_approval(job_id)
        self.activity.append(f"{job_id} 已载入两份固定 mock 样本，等待人工审批；没有执行渲染。")

    def job_action(self, job_id, action):
        if action == "load-fixture":
            self.load_fixture(job_id)
            return
        record = self.record(job_id)
        if action == "cancel":
            record.job = self.queue.cancel(job_id)
        else:
            record.job = self.queue.retry(job_id, ExecutionMode.MOCK)
            record.aovs, record.variants, record.proposals, record.images = [], [], [], {}
        self.activity.append(f"{job_id}：{action}（仅本地 mock 队列）。")

    def approve_variant(self, job_id, variant_id):
        record = self.record(job_id)
        variant = next((item for item in record.variants if item.variant_id == variant_id), None)
        if variant is None:
            raise KeyError("找不到该变体。")
        approved = self.domain.approve_variant(variant, approved_by="lab-local-reviewer")
        record.variants = [approved if item.variant_id == variant_id else item for item in record.variants]
        self.activity.append(f"已审批 mock 变体 {variant_id}；未写回工程。")

    def propose(self, job_id, request: LabProposalInput):
        record = self.record(job_id)
        variant = next((item for item in record.variants if item.variant_id == request.variant_id), None)
        if variant is None:
            raise KeyError("找不到该变体。")
        brief = self.fixture.brief.model_copy(update={"scene": record.job.scene})
        proposal = self.domain.propose_writeback(
            proposal_id="lab-proposal-" + uuid4().hex[:12], brief=brief, variant=variant,
            operations=[WritebackOperation(
                target=WritebackTarget.BLENDER, target_object_id="sceneops_light_porch",
                property=WritebackProperty.LIGHT_INTENSITY, previous_value=600,
                proposed_value=request.intensity,
            )],
            rationale=request.rationale, expected_result="提高门廊目标可见度，并保留门体轮廓。",
            risk="low", validation_plan="真实执行前需固定相机验证采集。",
            rollback_plan="将门廊灯强度恢复为 600。",
        )
        record.proposals.append(proposal)
        self.activity.append(f"已创建提案 {proposal.proposal_id}，等待审批。")

    def approve_proposal(self, job_id, proposal_id):
        record = self.record(job_id)
        proposal = next((item for item in record.proposals if item.proposal_id == proposal_id), None)
        if proposal is None:
            raise KeyError("找不到该提案。")
        approved = approve_writeback(
            proposal, changeset_id="lab-changeset-" + uuid4().hex[:12],
            approved_by="lab-local-reviewer", approved_at=datetime.now(timezone.utc),
        )
        record.proposals = [approved if item.proposal_id == proposal_id else item for item in record.proposals]
        self.activity.append(f"提案 {proposal_id} 已审批；工程写回仍为 blocked。")

    def compare(self, job_id, request: LabCompareInput):
        record = self.record(job_id)
        if request.before_id not in record.images or request.after_id not in record.images:
            raise KeyError("比较样本不存在，请先载入 mock 样本。")
        before, after = record.images[request.before_id], record.images[request.after_id]
        protected = compare_protected_region(
            "region_home_door", bytes(before.values), bytes(after.values), door_mask(), 0,
        )
        comparison = make_comparison(
            comparison_id="lab-compare-" + uuid4().hex[:12],
            before_artifact_id=request.before_id, after_artifact_id=request.after_id,
            scene=record.job.scene, before=bytes(before.values), after=bytes(after.values),
            protected_regions=[protected], changed_object_ids=["sceneops_light_porch"],
            execution_mode=ExecutionMode.MOCK,
        )
        return LabComparison(comparison=comparison, before=before, after=after)
