"""Durable local drafts composed with existing engine/release services."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from engine_unity import ChangeSet, UnityWorkbenchService
from .adapters import StaticArtifactCatalog
from .repository import InMemoryReleaseRepository
from .service import BuildReleaseService
from .requests import RecordBuildRequest, CreateCandidateRequest
from .models_build import BuildMatrix, BuildRun, BuildManifest
from .models_release import ReleaseGate
from .workbench_models import ProposalInput, LocalProposal, BuildScenario, WorkbenchSnapshot

class FixtureClock:
    def now(self):
        return datetime(2026, 9, 4, 8, 3, tzinfo=timezone.utc)

class WorkbenchConflict(ValueError):
    pass

class UnityBuildWorkbenchService:
    def __init__(self, database: Path):
        self.unity = UnityWorkbenchService()
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, content TEXT NOT NULL)")
        self.catalog = StaticArtifactCatalog({})
        self.release = BuildReleaseService(InMemoryReleaseRepository(), self.catalog, {}, FixtureClock())
        self.scenarios = {}
        fixture = Path(__file__).resolve().parents[3] / "fixtures/workbench-records.mock.json"
        for record in json.loads(fixture.read_text()):
            self.load_scenario(record)

    def connect(self):
        return sqlite3.connect(self.database)

    def load_scenario(self, record):
        matrix = BuildMatrix.model_validate(record["matrix"])
        runs = [BuildRun.model_validate(r) for r in record["runs"]]
        manifests = [BuildManifest.model_validate(m) for m in record["manifests"]]
        gates = [ReleaseGate.model_validate(g) for g in record["gates"]]
        for run, manifest in zip(runs, manifests):
            for artifact in [*manifest.artifacts, *manifest.test_evidence]:
                self.catalog.register_matching(artifact)
            self.release.record_build(RecordBuildRequest(matrix=matrix, run=run, manifest=manifest))
        candidate = self.release.create_candidate(CreateCandidateRequest(candidate_id="candidate.lab."+record["slug"],
            manifest_ids=[m.manifest_id for m in manifests], gates=gates,
            approved_change_set_ids=[c["change_set_id"] for c in record["change_sets"]]))
        self.scenarios[record["slug"]] = dict(slug=record["slug"], matrix=matrix, runs=runs, manifests=manifests, gates=gates, candidate=candidate)

    def default_proposal(self, slug):
        return LocalProposal(proposal_id=slug,revision=0,expected_revision=0,title="本地发布提案 · "+slug,
            notes="请审核 mock 构建记录。真实构建、测试和发布尚未执行。",target="local",updated_at=FixtureClock().now(),
            change_set=ChangeSet(change_set_id="chg_lab_"+slug,base_version="lab-mock-v1",command="unity.component_property.set",
                target_object_ids=["sobj_home_key","sinst_home_key_a"],previous_values={"value":False},
                proposed_values={"sceneops_id":"sobj_home_key","scene_instance_id":"sinst_home_key_a","component_type":"BoxCollider","property_path":"m_IsTrigger","value":True},
                rationale="提议将示例钥匙碰撞体设为触发器",expected_result="批准后钥匙可触发拾取",impact_scope="单个示例对象",risk="low",
                validation_plan=["人工检查触发范围；Unity 验证 pending approval"],rollback_plan=["恢复原 m_IsTrigger 值"],approval_state="pending"))

    def proposal(self, slug):
        if slug not in self.scenarios:
            raise KeyError(slug)
        with self.connect() as db:
            row=db.execute("SELECT content FROM proposals WHERE id=?",(slug,)).fetchone()
        return LocalProposal.model_validate_json(row[0]) if row else self.default_proposal(slug)

    def snapshot(self):
        return WorkbenchSnapshot(unity=self.unity.snapshot(),scenarios=[BuildScenario(**s,proposal=self.proposal(slug)) for slug,s in self.scenarios.items()])

    def save(self, slug: str, request: ProposalInput):
        if slug not in self.scenarios:
            raise KeyError(slug)
        self.unity.preview(request.change_set)
        proposal = LocalProposal(**request.model_dump(),proposal_id=slug,revision=request.expected_revision+1,updated_at=datetime.now(timezone.utc))
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT revision FROM proposals WHERE id=?",(slug,)).fetchone()
            revision=row[0] if row else 0
            if revision != request.expected_revision:
                raise WorkbenchConflict("提案已被其他窗口修改；请刷新后重新编辑。")
            db.execute("INSERT INTO proposals VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,content=excluded.content",(slug,proposal.revision,proposal.model_dump_json()))
        return proposal
