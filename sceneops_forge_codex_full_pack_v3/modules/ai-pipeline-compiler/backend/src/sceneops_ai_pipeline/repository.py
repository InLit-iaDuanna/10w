"""V5 proposal and derived-record storage; it does not own kernel run tables."""
import sqlite3
from pathlib import Path
from sceneops_harness import RecoveryPlan, DistilledWorkflow, HarnessError
from .schemas import PipelineProposal


class ProposalRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS ai_harness_records (
                project_id TEXT NOT NULL, record_id TEXT NOT NULL, kind TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY(project_id,record_id))""")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def save(self, project_id, kind, value):
        with self.connect() as connection:
            connection.execute("INSERT INTO ai_harness_records VALUES (?,?,?,?)",
                (project_id, value.id, kind, value.model_dump_json()))
        return value

    def get(self, project_id, record_id, kind, model):
        with self.connect() as connection:
            row = connection.execute("SELECT payload FROM ai_harness_records WHERE project_id=? AND record_id=? AND kind=?",
                (project_id, record_id, kind)).fetchone()
        if row is None:
            raise HarnessError("RECORD_NOT_FOUND", "当前项目中没有此记录。")
        return model.model_validate_json(row[0])

    def list(self, project_id, kind, model):
        with self.connect() as connection:
            rows = connection.execute("SELECT payload FROM ai_harness_records WHERE project_id=? AND kind=? ORDER BY rowid DESC LIMIT 100",
                (project_id, kind)).fetchall()
        return [model.model_validate_json(row[0]) for row in rows]

    def proposal(self, project_id, record_id):
        return self.get(project_id, record_id, "proposal", PipelineProposal)

    def recovery(self, project_id, record_id):
        return self.get(project_id, record_id, "recovery", RecoveryPlan)

    def workflows(self, project_id):
        return self.list(project_id, "workflow", DistilledWorkflow)
