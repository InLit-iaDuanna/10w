import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from .unified_schemas import AIConversation, AIMessage, AISettings

class AIRepository:
    """Owns only conversation tables; no cross-module database access."""
    def __init__(self, database_path: str | Path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS conversation_ai_settings (
                    id INTEGER PRIMARY KEY CHECK(id=1), model TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS conversation_ai_messages (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
                    scope TEXT NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL,
                    model TEXT NOT NULL, mode TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS conversation_ai_scope ON conversation_ai_messages(scope,sequence);
            ''')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def settings(self) -> AISettings:
        with self.connect() as connection:
            row = connection.execute('SELECT model FROM conversation_ai_settings WHERE id=1').fetchone()
        return AISettings(model=row['model']) if row else AISettings()

    def save_settings(self, settings: AISettings) -> AISettings:
        with self.connect() as connection:
            connection.execute('INSERT INTO conversation_ai_settings VALUES(1,?) '
                'ON CONFLICT(id) DO UPDATE SET model=excluded.model', (settings.model,))
        return settings

    def conversation(self, project_id: str | None) -> AIConversation:
        with self.connect() as connection:
            rows = connection.execute('SELECT id,role,text,model,mode,created_at FROM conversation_ai_messages '
                'WHERE scope=? ORDER BY sequence', (self.scope(project_id),)).fetchall()
        return AIConversation(project_id=project_id, messages=[AIMessage(**dict(row)) for row in rows])

    @staticmethod
    def scope(project_id):
        return 'pre_project' if project_id is None else 'project:' + project_id

    def append_exchange(self, project_id: str | None, prompt: str, reply: str, model: str):
        # Atomic successful exchanges prevent failed/retried requests duplicating historical prompts.
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            for role, text, mode in [('user', prompt, 'planned'), ('assistant', reply, 'live')]:
                connection.execute('INSERT INTO conversation_ai_messages '
                    '(id,scope,role,text,model,mode,created_at) VALUES(?,?,?,?,?,?,?)',
                    (str(uuid4()), self.scope(project_id), role, text, model, mode, now))
