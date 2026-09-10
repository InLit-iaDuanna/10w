"""Durable native Lookdev documents and canonical TypeScript validation boundary."""
import asyncio
import json
import shutil
import sqlite3
import threading
from uuid import uuid4
from .lookdev_glb import normalize_glb
from pathlib import Path
from .lookdev_models import LookdevDocument, LookdevError, LookdevProposal, LookdevTurn, FinishLookdevTurnRequest, utc_now


class NodeLookdevValidator:
    def __init__(self, root: Path):
        self.root = root
        self.entry = root / 'modules/vfx-shader/scripts/validate-lookdev.ts'

    async def __call__(self, payload):
        node = shutil.which('node')
        if not node:
            raise LookdevError('VALIDATOR_UNAVAILABLE', '材质校验运行环境不可用。', 503)
        process = await asyncio.create_subprocess_exec(node, '--import', 'tsx', str(self.entry),
            cwd=self.root / 'modules/vfx-shader/frontend', stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(json.dumps(payload).encode()), 120 if payload.get('action') == 'export' else 30)
        except BaseException as error:
            if process.returncode is None:
                process.kill()
                await process.wait()
            if isinstance(error, TimeoutError):
                raise LookdevError('VALIDATOR_TIMEOUT', '材质校验超时，当前内容已保留。', 503) from error
            raise
        try:
            result = json.loads(stdout)
        except ValueError as error:
            raise LookdevError('VALIDATOR_UNAVAILABLE', '材质校验器未返回有效结果。', 503) from error
        if process.returncode or not result.get('valid'):
            raise LookdevError('LOOKDEV_INVALID', result.get('error', '材质校验失败。'), 422)
        return result


class LookdevService:
    def __init__(self, database, workspace, catalog, provider, validator, application=None, record_exchange=None, on_applied=None):
        self.record_exchange = record_exchange
        self.on_applied = on_applied
        self.turn_lock = threading.RLock()
        self.database, self.workspace, self.catalog = Path(database), workspace, catalog
        self.provider, self.validator, self.application = provider, validator, application
        if application is not None:
            application.source = self.source
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS lookdev_turns (project_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(project_id,id))')
            db.execute('CREATE TABLE IF NOT EXISTS lookdev_sources (project_id TEXT, asset_id TEXT, version INTEGER, path TEXT, PRIMARY KEY(project_id,asset_id,version))')
            db.execute('CREATE TABLE IF NOT EXISTS lookdev_documents (project_id TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(project_id,id,version))')
            db.execute('CREATE TABLE IF NOT EXISTS lookdev_applications (project_id TEXT NOT NULL, document_id TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(project_id,document_id))')

    def connect(self):
        return sqlite3.connect(self.database, timeout=30)

    def require_project(self, project_id):
        if not self.workspace.exists(project_id):
            raise LookdevError('PROJECT_NOT_FOUND', '项目不存在。', 404)

    def source(self, project_id, asset_id, version):
        self.require_project(project_id)
        entry = self.catalog.get(project_id, asset_id)
        selected = next((item for item in entry.versions if item.source_version == version), None)
        if selected is None:
            raise LookdevError('ASSET_VERSION_NOT_FOUND', '模型版本不存在。', 404)
        if not selected.preview_path:
            raise LookdevError('ASSET_SOURCE_UNAVAILABLE', '模型源文件不可用。', 404)
        source = Path(selected.preview_path)
        if not source.is_absolute():
            binding = self.workspace.get_card_worktree(project_id, entry.card_id)
            root = Path(binding['worktree_path']).resolve(strict=True)
            source = root / source
            if source.is_symlink() or not source.resolve().is_relative_to(root):
                raise LookdevError('ASSET_SOURCE_UNAVAILABLE', '模型源路径不安全。', 404)
        if source.is_symlink() or not source.is_file():
            raise LookdevError('ASSET_SOURCE_UNAVAILABLE', '模型源文件不可用。', 404)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT path FROM lookdev_sources WHERE project_id=? AND asset_id=? AND version=?', (project_id, asset_id, version)).fetchone()
            if row:
                return Path(row[0])
            directory = self.database.parent / 'lookdev-sources'
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / (uuid4().hex + '.glb')
            path.write_bytes(normalize_glb(source.read_bytes()))
            db.execute('INSERT INTO lookdev_sources VALUES(?,?,?,?)', (project_id, asset_id, version, str(path)))
        return path

    def get(self, project_id, document_id, version=None):
        self.require_project(project_id)
        query = 'SELECT body FROM lookdev_documents WHERE project_id=? AND id=?'
        args = [project_id, document_id]
        if version is not None:
            query += ' AND version=?'
            args.append(version)
        with self.connect() as db:
            row = db.execute(query + ' ORDER BY version DESC LIMIT 1', args).fetchone()
        if not row:
            raise LookdevError('LOOKDEV_NOT_FOUND', '尚未保存材质文档。', 404)
        return LookdevDocument.model_validate_json(row[0])

    def list(self, project_id, asset_id=None, scene_instance_id=None):
        self.require_project(project_id)
        with self.connect() as db:
            rows = db.execute('SELECT body FROM lookdev_documents d WHERE project_id=? AND version=(SELECT MAX(version) FROM lookdev_documents x WHERE x.project_id=d.project_id AND x.id=d.id)', (project_id,)).fetchall()
        docs = [LookdevDocument.model_validate_json(row[0]) for row in rows]
        return [doc for doc in docs if (asset_id is None or doc.target.asset_id == asset_id)
                and (scene_instance_id is None or doc.target.scene_instance_id == scene_instance_id)]

    async def save(self, project_id, request):
        doc = request.document
        self.require_project(project_id)
        if doc.project_id != project_id:
            raise LookdevError('PROJECT_MISMATCH', '文档不属于当前项目。', 422)
        self.source(project_id, doc.target.asset_id, doc.target.asset_version)
        checked = await self.validator({'action': 'validate', 'project': doc.state})
        runtime = await self.validator({'action': 'generate-game', 'project': checked['project']})
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT version, body FROM lookdev_documents WHERE project_id=? AND id=? ORDER BY version DESC LIMIT 1', (project_id, doc.id)).fetchone()
            actual = row[0] if row else 0
            if actual != request.expected_version or doc.version != request.expected_version:
                raise LookdevError('LOOKDEV_VERSION_CONFLICT', '材质版本已更新，草稿已保留，请重新读取后保存。')
            if row and LookdevDocument.model_validate_json(row[1]).target != doc.target:
                raise LookdevError('LOOKDEV_TARGET_CHANGED', '已有文档不能更换资产或材质绑定，请另存文档。')
            saved = doc.model_copy(update={'state': checked['project'], 'runtime_module': runtime['code'], 'version': actual + 1, 'updated_at': utc_now()})
            db.execute('INSERT INTO lookdev_documents VALUES(?,?,?,?)', (project_id, doc.id, saved.version, saved.model_dump_json()))
        return saved

    async def propose(self, project_id, request):
        doc = request.document
        self.require_project(project_id)
        if doc.project_id != project_id:
            raise LookdevError('PROJECT_MISMATCH', '文档不属于当前项目。', 422)
        self.source(project_id, doc.target.asset_id, doc.target.asset_version)
        await self.validator({'action': 'validate', 'project': doc.state})
        material_ids = request.material_ids
        if not material_ids or not set(material_ids) <= {m['id'] for m in doc.state.get('materials', [])}:
            raise LookdevError('MATERIAL_SCOPE_REQUIRED', '请选择有效材质后再发送。', 422)
        scope = {'materialIds': material_ids, 'lightIds': [light['id'] for light in doc.state.get('lights', [])] if request.allow_lighting else [], 'lighting': request.allow_lighting}
        context = await self.validator({'action': 'proposal-context', 'project': doc.state,
            'scope': scope, 'selectedMaterialId': material_ids[0],
            **({'selectedObjectId': doc.target.sceneops_id} if doc.target.sceneops_id else {})})
        turn = LookdevTurn(id=request.turn_id or str(uuid4()), prompt=request.prompt, target=doc.target, model=request.model or '')
        if hasattr(self.provider, 'settings'):
            settings = self.provider.settings()
            turn.provider, turn.model = settings.provider, request.model or settings.model
        with self.connect() as db:
            try:
                db.execute('INSERT INTO lookdev_turns VALUES(?,?,?)', (project_id, turn.id, turn.model_dump_json()))
            except sqlite3.IntegrityError as error:
                raise LookdevError('TURN_EXISTS', '该材质请求已提交。') from error
        prompt = context['prompt'] + '\n用户要求：' + request.prompt
        try:
            proposal = await self.provider.structured(prompt, context['schema'], model=request.model, purpose='lookdev')
            status = proposal.get('status', 'applied' if proposal.get('operations') else 'noop')
            if status not in ('applied', 'declined', 'noop'):
                raise LookdevError('INVALID_PROPOSAL', '材质提案状态无效。', 422)
            if status in ('declined', 'noop'):
                if proposal.get('operations'):
                    raise LookdevError('INVALID_PROPOSAL', '未应用的提案不能包含操作。', 422)
                result = LookdevProposal(turn_id=turn.id, operations=[], summary=proposal['summary'],
                    base_version=doc.version, target=doc.target, state=doc.state, status=status)
            else:
                checked = await self.validator({'action': 'apply', 'project': doc.state,
                    'operations': proposal['operations'], 'source': 'ai', 'summary': proposal['summary'], 'scope': scope})
                result = LookdevProposal(turn_id=turn.id, operations=checked['operations'],
                    summary=proposal['summary'], base_version=doc.version, target=doc.target, state=checked['project'])
            turn.summary, turn.status = result.summary, 'proposed'
            with self.turn_lock, self.connect() as db:
                existing = LookdevTurn.model_validate_json(db.execute(
                    'SELECT body FROM lookdev_turns WHERE project_id=? AND id=?', (project_id, turn.id)).fetchone()[0])
                if existing.status == 'cancelled':
                    raise asyncio.CancelledError()
                if existing.status != 'pending':
                    raise LookdevError('TURN_FINISHED', '材质请求已经结束。')
                db.execute('UPDATE lookdev_turns SET body=? WHERE project_id=? AND id=?',
                    (turn.model_dump_json(), project_id, turn.id))
            return result
        except BaseException as error:
            status = 'cancelled' if isinstance(error, asyncio.CancelledError) else 'failed'
            self.finish_turn(project_id, turn.id, FinishLookdevTurnRequest(status=status,
                summary='材质修改已取消。' if status == 'cancelled' else '材质提案生成或校验失败，原画面已保留。'))
            raise

    def recover_turns(self):
        with self.connect() as db:
            rows = db.execute('SELECT project_id, body FROM lookdev_turns').fetchall()
        for project_id, body in rows:
            turn = LookdevTurn.model_validate_json(body)
            if turn.status in ('pending', 'proposed') and self.workspace.exists(project_id):
                self.finish_turn(project_id, turn.id, FinishLookdevTurnRequest(
                    status='failed', summary='上次材质请求因工作台重启中断，请重新发送。'))

    def history(self, project_id):
        self.require_project(project_id)
        with self.connect() as db:
            return [LookdevTurn.model_validate_json(row[0]) for row in db.execute(
                'SELECT body FROM lookdev_turns WHERE project_id=? ORDER BY rowid', (project_id,))]

    def finish_turn(self, project_id, turn_id, request):
        self.require_project(project_id)
        with self.turn_lock:
            turn = next((item for item in self.history(project_id) if item.id == turn_id), None)
            if turn is None:
                raise LookdevError('TURN_NOT_FOUND', '材质请求不存在。', 404)
            if turn.status not in ('pending', 'proposed'):
                return turn
            if request.status == 'applied' and turn.status != 'proposed':
                raise LookdevError('PROPOSAL_REQUIRED', '尚未生成有效材质提案。')
            turn.status = request.status
            turn.summary = request.summary or turn.summary or {'cancelled': '材质修改已取消。', 'failed': '材质修改失败，原画面已保留。'}.get(request.status, '')
            if self.record_exchange is not None:
                try:
                    self.record_exchange(project_id, turn.prompt, turn.summary, turn.model,
                        turn.provider, message_ids=(turn.id + '-user', turn.id + '-assistant'))
                except sqlite3.IntegrityError:
                    # Existing unique message IDs make retries after an interrupted finish idempotent.
                    pass
            with self.connect() as db:
                db.execute('UPDATE lookdev_turns SET body=? WHERE project_id=? AND id=?', (turn.model_dump_json(), project_id, turn_id))
            return turn

    def compose_geometry_materials(self, project_id, version, data):
        from .lookdev_glb import apply_pbr
        if not version.lookdev_document_id:
            return data
        document = self.get(project_id, version.lookdev_document_id, version.lookdev_document_version)
        return apply_pbr(data, document.state)

    def runtime_bindings(self, project_id, workspace_id=None):
        bindings = self.bindings(project_id)
        known = {(b['asset_id'], b['asset_version']) for b in bindings}
        for asset in self.catalog.list(project_id):
            for version in asset.versions:
                if version.lookdev_document_id and (asset.id, version.source_version) not in known:
                    document = self.get(project_id, version.lookdev_document_id, version.lookdev_document_version)
                    bindings.append(dict(asset_id=asset.id, asset_version=version.source_version,
                        document_id=document.id, document_version=document.version,
                        scene_instance_id=None, state=document.state, runtime_module=document.runtime_module or ''))
        if workspace_id is not None:
            bindings = [item for item in bindings if self.catalog.get(project_id, item['asset_id']).workspace_id == workspace_id]
        return bindings

    def bindings(self, project_id):
        self.require_project(project_id)
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT body FROM lookdev_applications WHERE project_id=?', (project_id,))]

    def apply(self, project_id, request):
        doc = self.get(project_id, request.document_id, request.document_version)
        if self.application is None:
            raise LookdevError('APPLICATION_UNAVAILABLE', '游戏应用服务不可用。', 503)
        result = self.application.apply(project_id, doc, request)
        with self.connect() as db:
            db.execute('INSERT INTO lookdev_applications VALUES(?,?,?) ON CONFLICT(project_id,document_id) DO UPDATE SET body=excluded.body', (project_id, doc.id, result.model_dump_json()))
        if self.on_applied:
            self.on_applied(project_id, result)
        return result

    async def export(self, project_id, request):
        from .lookdev_export import export_document
        return await export_document(self, project_id, request)

    def export_file(self, project_id, artifact_id):
        from .lookdev_export import export_file
        return export_file(self, project_id, artifact_id)
