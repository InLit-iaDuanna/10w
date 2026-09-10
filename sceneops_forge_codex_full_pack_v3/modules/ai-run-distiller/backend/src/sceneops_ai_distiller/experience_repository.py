"""Experience data lives beside existing records, never in their private tables."""
import json
import sqlite3
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path

from .experience_topics import topic_text
from .experience_models import (ExperienceEntry, ExperienceRevision, ExperienceSettings,
                                ExperienceUse, LearningBatch, utc_now)


class ExperienceError(ValueError):
    def __init__(self, code, message, status_code=409):
        super().__init__(message)
        self.code, self.status_code = code, status_code


def scope_key(project_id):
    return project_id if project_id is not None else "@pre-project"


class ExperienceRepository:
    def __init__(self, database):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS experience_memory_requests (
                    scope_key TEXT NOT NULL, request_id TEXT NOT NULL, event_id TEXT NOT NULL,
                    request_body TEXT NOT NULL, PRIMARY KEY(scope_key,request_id));
                CREATE TABLE IF NOT EXISTS experience_memory_events (
                    id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experience_settings (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experience_entries (
                    id TEXT PRIMARY KEY, project_id TEXT, scope TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experience_revisions (
                    entry_id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL,
                    reason TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(entry_id, revision));
                CREATE TABLE IF NOT EXISTS experience_seed_imports (
                    bundle_id TEXT NOT NULL, entry_id TEXT NOT NULL, PRIMARY KEY(bundle_id, entry_id));
                CREATE VIRTUAL TABLE IF NOT EXISTS experience_search USING fts5(
                    entry_id UNINDEXED, title, content, applicability, domains, tokenize='trigram');
                CREATE TABLE IF NOT EXISTS experience_sources (
                    scope_key TEXT NOT NULL, id TEXT NOT NULL, project_id TEXT, body TEXT NOT NULL,
                    batch_id TEXT, processed INTEGER NOT NULL DEFAULT 0, received_at TEXT NOT NULL,
                    PRIMARY KEY(scope_key,id));
                CREATE TABLE IF NOT EXISTS experience_batches (
                    id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experience_review_checkpoints (
                    batch_id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experience_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT NOT NULL, day TEXT NOT NULL,
                    provider TEXT NOT NULL, model TEXT NOT NULL, started_at TEXT NOT NULL,
                    completed_at TEXT, tokens INTEGER, cost_usd REAL, error TEXT);
                CREATE TABLE IF NOT EXISTS experience_uses (
                    id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, use_key TEXT NOT NULL, body TEXT NOT NULL,
                    UNIQUE(scope_key,use_key));
            ''')
            db.execute('INSERT OR IGNORE INTO experience_settings VALUES(1,?)',
                       (ExperienceSettings().model_dump_json(),))
        self.import_seed()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def settings(self, db=None):
        if db is None:
            with self.connect() as db:
                return self.settings(db)
        return ExperienceSettings.model_validate_json(db.execute('SELECT body FROM experience_settings WHERE id=1').fetchone()[0])

    def set_settings(self, update):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            data = self.settings(db).model_dump()
            data.update(update.model_dump(exclude_none=True))
            value = ExperienceSettings.model_validate(data)
            db.execute('UPDATE experience_settings SET body=? WHERE id=1', (value.model_dump_json(),))
        return value

    @staticmethod
    def _write(db, entry, reason):
        db.execute('INSERT INTO experience_entries VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                   'project_id=excluded.project_id,scope=excluded.scope,body=excluded.body',
                   (entry.id, entry.project_id, entry.scope, entry.model_dump_json()))
        db.execute('INSERT INTO experience_revisions VALUES(?,?,?,?,?)',
                   (entry.id, entry.revision, entry.model_dump_json(), reason, entry.updated_at))
        db.execute('DELETE FROM experience_search WHERE entry_id=?', (entry.id,))
        db.execute('INSERT INTO experience_search VALUES(?,?,?,?,?)',
                   (entry.id, entry.title, entry.content, entry.applicability, ' '.join(entry.domains) + ' ' + topic_text(entry.topics)))

    def import_seed(self):
        seed = json.loads(files('sceneops_ai_distiller').joinpath('resources/experience-seed-v1.json').read_text(encoding='utf-8'))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for value in seed['entries']:
                entry = ExperienceEntry.model_validate(value)
                added = db.execute('INSERT OR IGNORE INTO experience_seed_imports VALUES(?,?)',
                                   (seed['bundle_id'], entry.id)).rowcount
                stored = db.execute('SELECT body FROM experience_entries WHERE id=?', (entry.id,)).fetchone()
                if added and not stored:
                    self._write(db, entry, '导入历史经验；验证仅属于源项目历史。')
                elif stored and 'topics' not in json.loads(stored[0]) and entry.topics:
                    # Upgrade only previously absent metadata, preserving user text and disabled state.
                    current = ExperienceEntry.model_validate_json(stored[0])
                    current.topics = entry.topics
                    current.revision += 1
                    current.updated_at = utc_now()
                    self._write(db, current, '补充主题分类；保留原内容、证据与启用状态。')

    @staticmethod
    def read(db, entry_id):
        row = db.execute('SELECT body FROM experience_entries WHERE id=?', (entry_id,)).fetchone()
        if row is None:
            raise ExperienceError('EXPERIENCE_NOT_FOUND', '经验不存在。', 404)
        return ExperienceEntry.model_validate_json(row[0])

    @staticmethod
    def check_scope(entry, project_id):
        if entry.scope != 'shared' and entry.project_id != project_id:
            raise ExperienceError('EXPERIENCE_NOT_FOUND', '当前项目不可读取此经验。', 404)

    def get(self, entry_id, project_id):
        with self.connect() as db:
            entry = self.read(db, entry_id)
        self.check_scope(entry, project_id)
        return entry

    def list(self, project_id, *, include_disabled=False):
        with self.connect() as db:
            rows = db.execute("SELECT body FROM experience_entries WHERE scope='shared' OR project_id IS ?", (project_id,)).fetchall()
        result = [ExperienceEntry.model_validate_json(row[0]) for row in rows]
        return [e for e in result if include_disabled or e.enabled]

    def ranked_ids(self, match):
        with self.connect() as db:
            return [row[0] for row in db.execute('SELECT entry_id FROM experience_search WHERE experience_search MATCH ? '
                'ORDER BY bm25(experience_search,0,4,1,2,3)', (match,))]

    def edit(self, entry_id, project_id, expected_revision, updates, *, reason, restore_revision=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = self.read(db, entry_id)
            self.check_scope(prior, project_id)
            if prior.revision != expected_revision:
                raise ExperienceError('EXPERIENCE_REVISION_CONFLICT', '经验已更新，请重新读取；你的草稿仍可保留。')
            if restore_revision is not None:
                row = db.execute('SELECT body FROM experience_revisions WHERE entry_id=? AND revision=?',
                                 (entry_id, restore_revision)).fetchone()
                if not row:
                    raise ExperienceError('EXPERIENCE_REVISION_NOT_FOUND', '修订不存在。', 404)
                updates = ExperienceEntry.model_validate_json(row[0]).model_dump()
            data = prior.model_dump()
            data.update(updates)
            data.update(id=prior.id, project_id=prior.project_id, scope=prior.scope,
                        revision=prior.revision + 1, created_at=prior.created_at, updated_at=utc_now())
            entry = ExperienceEntry.model_validate(data)
            self._write(db, entry, reason)
        return entry

    def revisions(self, entry_id, project_id):
        self.get(entry_id, project_id)
        with self.connect() as db:
            rows = db.execute('SELECT body,reason,created_at FROM experience_revisions WHERE entry_id=? ORDER BY revision DESC', (entry_id,)).fetchall()
        return [ExperienceRevision(entry=ExperienceEntry.model_validate_json(r[0]), reason=r[1], created_at=r[2]) for r in rows]

    def save_use(self, use):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO experience_uses VALUES(?,?,?,?)',
                       (use.id, scope_key(use.project_id), use.use_key, use.model_dump_json()))
            row = db.execute('SELECT body FROM experience_uses WHERE scope_key=? AND use_key=?',
                             (scope_key(use.project_id), use.use_key)).fetchone()
        return ExperienceUse.model_validate_json(row[0])

    def exact_uses(self, project_id, key):
        with self.connect() as db:
            rows = db.execute("SELECT body FROM experience_uses WHERE scope_key=? AND "
                "(use_key=? OR json_extract(body,'$.origin_key')=?) ORDER BY rowid DESC",
                (scope_key(project_id), key, key)).fetchall()
        return [ExperienceUse.model_validate_json(row[0]) for row in rows]

    def uses(self, project_id, prefix):
        with self.connect() as db:
            # instr performs literal prefix matching; user % and _ are not SQL wildcards.
            rows = db.execute('SELECT body FROM experience_uses WHERE scope_key=? AND instr(use_key,?)=1 ORDER BY rowid DESC LIMIT 100',
                              (scope_key(project_id), prefix)).fetchall()
        return [ExperienceUse.model_validate_json(row[0]) for row in rows]

    @staticmethod
    def batch_write(db, batch):
        db.execute('INSERT INTO experience_batches VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                   (batch.id, scope_key(batch.project_id), batch.model_dump_json()))

    def batch_state(self, batch, status, reason=''):
        batch.status, batch.reason, batch.updated_at = status, reason, utc_now()
        with self.connect() as db:
            self.batch_write(db, batch)
        return batch

    def reserve_call(self, batch, day, provider, model):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            settings = self.settings(db)
            if not settings.learn_enabled:
                raise ExperienceError('EXPERIENCE_LEARNING_PAUSED', '自动学习已关闭。')
            used = db.execute('SELECT count(*) FROM experience_calls WHERE day=?', (day,)).fetchone()[0]
            batch_calls = db.execute('SELECT count(*) FROM experience_calls WHERE batch_id=?', (batch.id,)).fetchone()[0]
            if batch_calls >= settings.batch_call_limit:
                raise ExperienceError('EXPERIENCE_BATCH_EXHAUSTED', '本批学习调用次数已用尽；原材料与结果保留。')
            if used >= settings.daily_call_limit:
                raise ExperienceError('EXPERIENCE_BUDGET_EXHAUSTED', '学习调用达到限额，待额度恢复后处理。')
            cursor = db.execute('INSERT INTO experience_calls(batch_id,day,provider,model,started_at) VALUES(?,?,?,?,?)',
                               (batch.id, day, provider, model, utc_now()))
            batch.calls = batch_calls + 1
            self.batch_write(db, batch)
            return cursor.lastrowid

    def finish_call(self, call_id, *, tokens=None, cost=None, error=None):
        with self.connect() as db:
            db.execute('UPDATE experience_calls SET completed_at=?,tokens=COALESCE(?,tokens),cost_usd=COALESCE(?,cost_usd),error=? WHERE id=?',
                       (utc_now(), tokens, cost, error, call_id))

    def batches(self):
        with self.connect() as db:
            rows = db.execute('SELECT body FROM experience_batches ORDER BY rowid DESC LIMIT 50').fetchall()
        return [LearningBatch.model_validate_json(r[0]) for r in rows]
