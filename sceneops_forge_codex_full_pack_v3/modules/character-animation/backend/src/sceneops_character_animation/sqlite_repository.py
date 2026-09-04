"""Project-scoped durable implementation of the module VersionRepository."""
import sqlite3
from .animation_models import AnimationClipSpec
from .character_models import RigVersion
from .errors import InvalidVersionError


class SqliteVersionRepository:
    def __init__(self, database, project_id):
        self.database, self.project_id = database, project_id
        with sqlite3.connect(database) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS character_versions
                (project_id TEXT NOT NULL, kind TEXT NOT NULL, version_id TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY(project_id,kind,version_id))""")

    def _save(self, kind, identity, value):
        with sqlite3.connect(self.database) as connection:
            connection.execute("""INSERT INTO character_versions VALUES (?,?,?,?)
                ON CONFLICT(project_id,kind,version_id) DO UPDATE SET payload=excluded.payload""",
                (self.project_id, kind, identity, value.model_dump_json()))

    def _get(self, kind, identity, model):
        with sqlite3.connect(self.database) as connection:
            row = connection.execute("SELECT payload FROM character_versions WHERE project_id=? AND kind=? AND version_id=?",
                (self.project_id, kind, identity)).fetchone()
        if not row:
            raise InvalidVersionError("当前项目中没有此版本。", {"version_id": identity})
        return model.model_validate_json(row[0])

    def save_rig(self, rig):
        self._save("rig", rig.rig_version_id, rig)

    def save_clip(self, clip):
        self._save("clip", clip.clip_version_id, clip)

    def get_rig(self, identity):
        return self._get("rig", identity, RigVersion)

    def get_clip(self, identity):
        return self._get("clip", identity, AnimationClipSpec)
