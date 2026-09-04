"""Project-scoped compare-and-swap repository for production plans."""
import sqlite3
from .models import ProductionPlan


class SqliteProductionPlanRepository:
    def __init__(self, database, project_id):
        self.database, self.project_id = database, project_id
        with sqlite3.connect(database) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS production_plans (
                project_id TEXT NOT NULL, plan_id TEXT NOT NULL, version INTEGER NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY(project_id,plan_id))""")

    def get(self, plan_id):
        with sqlite3.connect(self.database) as connection:
            row = connection.execute("SELECT payload FROM production_plans WHERE project_id=? AND plan_id=?",
                (self.project_id, plan_id)).fetchone()
        return ProductionPlan.model_validate_json(row[0]) if row else None

    def create(self, plan):
        with sqlite3.connect(self.database) as connection:
            cursor = connection.execute("INSERT OR IGNORE INTO production_plans VALUES (?,?,?,?)",
                (self.project_id, plan.plan_id, plan.plan_version, plan.model_dump_json()))
            return cursor.rowcount == 1

    def replace(self, plan, expected_version):
        with sqlite3.connect(self.database) as connection:
            cursor = connection.execute("UPDATE production_plans SET version=?,payload=? WHERE project_id=? AND plan_id=? AND version=?",
                (plan.plan_version, plan.model_dump_json(), self.project_id, plan.plan_id, expected_version))
            return cursor.rowcount == 1
