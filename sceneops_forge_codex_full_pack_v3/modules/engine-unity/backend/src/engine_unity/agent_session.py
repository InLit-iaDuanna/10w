"""Dedicated visible Unity 2022 session with owner-only, durable typed IPC."""
from __future__ import annotations

import json
import os
import re
import secrets
import signal
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .contracts import ImportAssetPayload

PINNED_EDITOR = Path('/Applications/Unity/Hub/Editor/2022.3.62f3c1/Unity.app/Contents/MacOS/Unity')
PACKAGE = Path(__file__).resolve().parents[5] / 'integrations/unity-package'


class UnityAgentSessionError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _inside(path: Path, root: Path) -> Path:
    path = Path(path).absolute()
    if not path.is_relative_to(root) or not path.resolve().is_relative_to(root):
        raise UnityAgentSessionError('UNITY_PATH_OUTSIDE_PROJECT', 'Path is outside the dedicated workspace.')
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise UnityAgentSessionError('UNITY_PATH_OUTSIDE_PROJECT', 'Symbolic links are not allowed in the dedicated workspace.')
        if part == root:
            break
    return path


def _write(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class UnityAgentSession:
    """Roots and authorization must come from the trusted task execution service."""

    def __init__(self, workspace_root: Path, state_root: Path, *, executable: Path | None = None):
        self.workspace_root = Path(workspace_root).absolute()
        _inside(self.workspace_root, self.workspace_root)
        self.state_root = Path(state_root).absolute()
        self.project_root = _inside(self.workspace_root / 'unity', self.workspace_root)
        self.mailbox = self.project_root / '.sceneops-agent'
        self.executable = Path(executable) if executable else PINNED_EDITOR
        if self.executable.suffix == '.app':
            self.executable /= 'Contents/MacOS/Unity'
        self._process = None
        self._cancel = threading.Event()
        self._lock = threading.RLock()
        self._config = None
        self._grant = None

    def bind_authorization(self, grant: dict) -> None:
        if grant.get('project_id') != self.workspace_root.name or grant.get('workspace_root') != str(self.workspace_root):
            raise UnityAgentSessionError('UNITY_AGENT_SCOPE_DENIED', 'Task grant does not match the dedicated workspace.')
        if not grant.get('task_id') or not grant.get('grant_id'):
            raise UnityAgentSessionError('UNITY_AGENT_AUTH_DENIED', 'Task grant identifiers are required.')
        self._grant = dict(grant)
        self._validate_grant()

    def _validate_grant(self, authorization=None) -> None:
        grant = self._grant
        if grant is None or datetime.fromisoformat(grant['expires_at'].replace('Z', '+00:00')) <= datetime.now(timezone.utc):
            raise UnityAgentSessionError('UNITY_AGENT_AUTH_DENIED', 'Task grant is missing or expired.')
        if authorization is not None:
            keys = ('task_id', 'grant_id', 'project_id', 'workspace_root', 'expires_at', 'allowed_capabilities')
            if any(authorization.get(key) != grant.get(key) for key in keys):
                raise UnityAgentSessionError('UNITY_AGENT_AUTH_DENIED', 'Action authorization differs from its bound task grant.')
            if authorization.get('capability_id') not in grant['allowed_capabilities']:
                raise UnityAgentSessionError('UNITY_AGENT_AUTH_DENIED', 'Capability is outside the task grant.')

    def _prepare(self) -> None:
        self._validate_grant()
        marker = self.mailbox / 'session.json'
        _inside(marker, self.workspace_root)
        if marker.exists():
            config = json.loads(marker.read_text())
            if config.get('created_by') != 'sceneops-agent-v1' or config.get('project_root') != str(self.project_root):
                raise UnityAgentSessionError('UNITY_AGENT_SCOPE_DENIED', 'Workspace ownership marker does not match.')
            self._config = config
            if config.get('grant') != self._grant:
                previous=config.get('grant', {})
                same_target=all(previous.get(k)==self._grant.get(k) for k in ('task_id','project_id','workspace_root','allowed_capabilities'))
                if (not same_target or not config.get('closed') or self._owned_pid_alive()
                        or 'unity.content.inspect' not in self._grant['allowed_capabilities']):
                    raise UnityAgentSessionError('UNITY_AGENT_AUTH_DENIED', 'Existing session belongs to another task grant.')
                for started in self.mailbox.glob('*.content-started.json'):
                    receipt=started.with_name(started.name.replace('.content-started.json','.result.json'))
                    if not receipt.is_file() or json.loads(receipt.read_text()).get('error_code')=='UNITY_OUTCOME_UNCERTAIN':
                        raise UnityAgentSessionError('UNITY_OUTCOME_UNCERTAIN','Reauthorization cannot replay unresolved content writes.')
                config['grant']=dict(self._grant)

            if config.get('closed'):
                if self._owned_pid_alive():
                    raise UnityAgentSessionError('UNITY_AGENT_SCOPE_DENIED', 'Retired session still has an Editor process; reconcile before rebinding.')
                config['session_id'] = 'session_' + uuid.uuid4().hex
                config['token'] = secrets.token_urlsafe(32)
                config['closed'] = False
                _write(marker, config)
            if not self._owned_pid_alive():
                self._configure_package()
            else:
                self._ensure_manifest_dependencies()
            return
        if self.project_root.exists() and any(self.project_root.iterdir()):
            raise UnityAgentSessionError('UNITY_AGENT_SCOPE_DENIED', 'Refusing to adopt an existing Unity project.')
        self._initialize_project()
        self.mailbox.mkdir(mode=0o700)
        (self.project_root / 'Staging').mkdir()
        self._configure_package()
        self._config = {'created_by': 'sceneops-agent-v1', 'project_root': str(self.project_root),
                        'project_id': self.workspace_root.name, 'session_id': 'session_' + uuid.uuid4().hex,
                        'token': secrets.token_urlsafe(32), 'grant': self._grant}
        _write(marker, self._config)

    def _initialize_project(self, timeout=180) -> None:
        """Let the installed Editor create its own project settings and built-in package set."""
        self._validate_grant()
        journal = _inside(self.workspace_root / 'unity-initialization.json', self.workspace_root)
        log_path = _inside(self.workspace_root / 'unity-initialization.log', self.workspace_root)
        if journal.exists():
            raise UnityAgentSessionError('UNITY_INITIALIZATION_INCOMPLETE',
                'A prior project initialization record exists; retain its project/log and use a fresh registered target.')
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        record = {'project_root': str(self.project_root), 'task_id': self._grant['task_id'],
                  'grant_id': self._grant['grant_id'], 'status': 'initializing'}
        _write(journal, record)
        try:
            launcher = _inside(self.workspace_root / 'unity-initialization.launcher.log', self.workspace_root)
            with launcher.open('xb') as output:
                self._process = subprocess.Popen([str(self.executable), '-batchmode', '-quit',
                    '-createProject', str(self.project_root), '-logFile', str(log_path)],
                    stdout=output, stderr=output, start_new_session=True)
                record['pid'] = self._process.pid
                _write(journal, record)
                deadline = time.monotonic() + timeout
                while self._process.poll() is None:
                    self._validate_grant()
                    if self._cancel.is_set():
                        raise UnityAgentSessionError('UNITY_CANCELLED', 'Owned project initialization was cancelled.')
                    if time.monotonic() >= deadline:
                        raise UnityAgentSessionError('UNITY_INITIALIZATION_TIMEOUT', 'Owned Editor project initialization timed out; retain its log and partial project.')
                    time.sleep(.1)
            self._validate_grant()
            log_text = log_path.read_text(errors='replace')
            if 'No valid Unity Editor license found.' in log_text:
                raise UnityAgentSessionError('UNITY_LICENSE_REQUIRED', 'Unity project initialization requires an active Editor license.')
            if self._process.returncode != 0:
                raise UnityAgentSessionError('UNITY_INITIALIZATION_FAILED', 'The owned Editor could not create the project; inspect unity-initialization.log.')
            version = _inside(self.project_root / 'ProjectSettings/ProjectVersion.txt', self.workspace_root)
            manifest = _inside(self.project_root / 'Packages/manifest.json', self.workspace_root)
            if not version.is_file() or not manifest.is_file() or 'm_EditorVersion: 2022.3.62f3c1' not in version.read_text():
                raise UnityAgentSessionError('UNITY_INITIALIZATION_FAILED', 'Editor did not produce the expected project settings and package manifest.')
            dependencies = json.loads(manifest.read_text()).get('dependencies', {})
            if not dependencies or any(not name.startswith('com.unity.modules.') for name in dependencies):
                raise UnityAgentSessionError('UNITY_UNEXPECTED_PACKAGES', 'Fresh Editor template contains packages outside its installed built-in modules; inspect before adoption.')
            record['status'] = 'succeeded'
            _write(journal, record)
        except Exception as error:
            if self._process is not None and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=5)
            record.update(status='failed', error_code=getattr(error, 'code', 'UNITY_INITIALIZATION_FAILED'))
            _write(journal, record)
            raise
        finally:
            if self._process is not None and self._process.poll() is not None:
                self._process = None

    def _configure_package(self) -> None:
        # Fixed application code is read from the bundled package, never from model input.
        # Unity ignores hidden embedded directories, common under local app-data roots.
        destination = _inside(self.project_root / 'Packages/com.sceneops.forge.unity', self.workspace_root)
        if destination.exists():
            for existing in destination.rglob('*'):
                _inside(existing, self.workspace_root)
            backup = _inside(self.mailbox / ('bundled-package.' + uuid.uuid4().hex), self.workspace_root)
            destination.rename(backup)
        self._ensure_manifest_dependencies()

    def _ensure_manifest_dependencies(self) -> None:
        manifest = _inside(self.project_root / 'Packages/manifest.json', self.workspace_root)
        content = json.loads(manifest.read_text()) if manifest.exists() else {'dependencies': {}}
        previous = json.dumps(content, sort_keys=True)
        content['dependencies']['com.sceneops.forge.unity'] = 'file:' + str(PACKAGE)
        content['dependencies']['com.unity.modules.audio'] = '1.0.0'
        # Unity 2022 ships InputLegacyModule as an engine assembly, not a UPM package.
        content['dependencies'].pop('com.unity.modules.inputlegacy', None)
        if json.dumps(content, sort_keys=True) != previous:
            _write(manifest, content)

    def start(self) -> dict:
        with self._lock:
            if not self.executable.is_file():
                raise UnityAgentSessionError('UNITY_EDITOR_UNAVAILABLE', 'Pinned Unity 2022.3.62f3c1 is not installed.')
            self._cancel.clear()
            self._prepare()
            if self._process is not None and self._process.poll() is not None:
                self._process = None
            try:
                state = self._inspect(timeout=2)
                return self._wait_ready(180) if state['compiling'] else state
            except UnityAgentSessionError as error:
                if error.code != 'UNITY_SESSION_TIMEOUT':
                    raise
            if not self._owned_pid_alive():
                editor_log = _inside(self.mailbox / 'editor.log', self.workspace_root)
                if editor_log.exists():
                    editor_log.rename(self.mailbox / ('editor.' + uuid.uuid4().hex + '.log'))
                with _inside(self.mailbox / 'launcher.log', self.workspace_root).open('ab') as log:
                    self._process = subprocess.Popen([str(self.executable), '-projectPath', str(self.project_root),
                        '-logFile', str(self.mailbox / 'editor.log')], stdout=log, stderr=log,
                        start_new_session=True)
                self._config['pid'] = self._process.pid
                _write(self.mailbox / 'session.json', self._config)
            return self._wait_ready(180)

    def _wait_ready(self, timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self._inspect(timeout=max(.1, deadline - time.monotonic()))
            if not state['compiling']:
                return state
            time.sleep(.5)
        raise UnityAgentSessionError('UNITY_COMPILATION_TIMEOUT', 'Unity is still compiling; inspect console and resume this session.')

    def _owned_pid_alive(self) -> bool:
        pid = (self._config or {}).get('pid')
        if pid and self._matches_project_process(pid):
            return True
        lock = _inside(self.project_root / 'Temp/UnityLockfile', self.workspace_root)
        if not lock.exists():
            return False
        # Unity's package Retry can relaunch with a new PID. The OS lock owner,
        # executable and exact project argument identify the same dedicated session.
        result = subprocess.run(['/usr/sbin/lsof', '-t', str(lock)], capture_output=True, text=True)
        owners = [int(value) for value in result.stdout.split() if value.isdecimal()]
        for owner in owners:
            if self._matches_project_process(owner):
                self._config['pid'] = owner
                _write(self.mailbox / 'session.json', self._config)
                return True
        if owners:
            raise UnityAgentSessionError('UNITY_PROJECT_ALREADY_OPEN', 'Dedicated project is locked by an unrecognized process; no second Editor was launched.')
        return False

    def _matches_project_process(self, pid):
        command = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
        if command.returncode != 0 or not command.stdout.strip().startswith(str(self.executable) + ' '):
            return False
        escaped = re.escape(str(self.project_root))
        return re.search(r'(?:^|\s)-projectPath\s+(?:' + escaped + r'|"' + escaped + r'")(?=\s+-|\s*$)', command.stdout) is not None

    def _exchange(self, request_id: str, command: str, *, batch=None, authorization=None, timeout=60) -> dict:
        self._validate_grant(authorization)
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}', request_id):
            raise UnityAgentSessionError('UNITY_INVALID_PAYLOAD', 'Invalid request identifier.')
        if self._config is None:
            marker = _inside(self.mailbox / 'session.json', self.workspace_root)
            if not marker.exists():
                raise UnityAgentSessionError('UNITY_SESSION_OFFLINE', 'Dedicated Unity session has not been started.')
            self._config = json.loads(marker.read_text())
        body = {'request_id': request_id, 'command': command, 'session_id': self._config['session_id'],
                'token': self._config['token'], 'batch': batch, 'authorization': authorization}
        request = _inside(self.mailbox / (request_id + '.request.json'), self.workspace_root)
        result = _inside(self.mailbox / (request_id + '.result.json'), self.workspace_root)
        if request.exists():
            if json.loads(request.read_text()) != body:
                raise UnityAgentSessionError('UNITY_IDEMPOTENCY_CONFLICT', 'Request ID already belongs to different command inputs.')
        else:
            _write(request, body)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._validate_grant()
            if self._cancel.is_set():
                _write(request.with_name(request_id + '.cancelled.json'), {'cancelled': True})
                raise UnityAgentSessionError('UNITY_CANCELLED', 'Dedicated Unity session was cancelled.')
            if result.exists():
                reply = json.loads(result.read_text())
                if reply['status'] != 'succeeded':
                    raise UnityAgentSessionError(reply['error_code'], reply['message'])
                return json.loads(reply['resultJson'])
            editor_log = self.mailbox / 'editor.log'
            if editor_log.exists() and 'No valid Unity Editor license found.' in editor_log.read_text(errors='replace') and (self._process is not None or self._owned_pid_alive()):
                raise UnityAgentSessionError('UNITY_LICENSE_REQUIRED', 'Unity reports no valid Editor license; activate/login in Unity Hub to continue.')
            if self._process is not None and self._process.poll() is not None:
                raise UnityAgentSessionError('UNITY_EDITOR_EXITED', self._failure_reason())
            time.sleep(.1)
        if command.startswith('unity.content.') and _inside(self.mailbox / (request_id + '.content-started.json'), self.workspace_root).exists():
            raise UnityAgentSessionError('UNITY_OUTCOME_UNCERTAIN', 'Content dispatch started without a durable result; inspect before recovery.')
        if command == 'unity.asset.import' and _inside(self.mailbox / (request_id + '.started.json'), self.workspace_root).exists():
            raise UnityAgentSessionError('UNITY_OUTCOME_UNCERTAIN', 'Import dispatch started without a durable result; inspect the project before recovery.')
        raise UnityAgentSessionError('UNITY_SESSION_TIMEOUT', self._failure_reason())

    def _failure_reason(self) -> str:
        path = self.mailbox / 'editor.log'
        if path.exists():
            lines = path.read_text(errors='replace').splitlines()
            relevant = [line for line in lines if 'error cs' in line.lower() or
                        'UnauthorizedAccessException' in line or 'Permission denied' in line]
            if relevant:
                return '\n'.join(relevant[-8:]).replace(self._config['token'], '[redacted]')
            if any('[Project] Loading completed' in line for line in lines) and not (
                self.project_root / 'Library/ScriptAssemblies/SceneOps.Forge.Unity.Editor.dll').exists():
                return 'UNITY_SESSION_TIMEOUT: Editor loaded, but the SceneOps bridge assembly was not imported; inspect the fixed bundled package visibility and package registration.'
        return 'UNITY_SESSION_TIMEOUT: no authenticated editor readiness response; compilation or connection may still be pending.'

    def _inspect(self, timeout=15) -> dict:
        result = self._exchange('inspect_' + uuid.uuid4().hex, 'inspect', timeout=timeout)
        if result.get('project_root') != str(self.project_root) or result.get('session_id') != self._config['session_id']:
            raise UnityAgentSessionError('UNITY_AGENT_SCOPE_DENIED', 'Editor replied for a different project/session.')
        for item in result.get('objects', []):
            item['dimensions_m'] = item['dimensions_meters']
        return {**result, 'mode': 'live', 'status': 'compiling' if result['compiling'] else 'connected',
                'tool': 'unity', 'workspace_root': str(self.workspace_root)}

    def inspect(self) -> dict:
        return self._inspect()

    def compose_prototype(self, *, request_id, spec, authorization):
        from .prototype_session import compose_prototype
        with self._lock:
            return compose_prototype(self, request_id=request_id, spec=spec, authorization=authorization)

    def inspect_prototype(self):
        from .prototype_session import inspect_prototype
        return inspect_prototype(self)

    def play_prototype(self, *, request_id, operation, input=None, authorization):
        from .prototype_session import play_prototype
        with self._lock:
            return play_prototype(self, request_id=request_id, operation=operation, input=input, authorization=authorization)

    def import_asset(self, *, request_id, asset_id, sceneops_id, fbx_path, manifest_path, authorization: dict) -> dict:
        with self._lock:
            state = self.inspect()
            required = ('task_id', 'grant_id', 'action_id', 'change_set_id', 'approval_id')
            self._validate_grant(authorization)
            if any(not authorization.get(key) for key in required) or authorization.get('capability_id') != 'unity.asset.import':
                raise UnityAgentSessionError('UNITY_AGENT_AUTH_DENIED', 'Task authorization must match the connected Unity import session.')
            authorization = {**authorization, 'session_id': state['session_id']}
            source = _inside(Path(fbx_path), self.workspace_root)
            manifest_source = _inside(Path(manifest_path), self.workspace_root)
            manifest = json.loads(manifest_source.read_text())
            if source.suffix.lower() != '.fbx' or manifest.get('source_asset_id') != asset_id or len(manifest.get('objects', [])) != 1 or manifest['objects'][0]['sceneops_id'] != sceneops_id:
                raise UnityAgentSessionError('UNITY_INVALID_PAYLOAD', 'FBX and manifest must contain the requested asset and one source identity.')
            if not re.fullmatch(r'ast_[A-Za-z0-9_.-]+', asset_id):
                raise UnityAgentSessionError('UNITY_INVALID_PAYLOAD', 'Invalid asset identifier.')
            staged = _inside(self.project_root / 'Staging' / (asset_id + '.fbx'), self.workspace_root)
            sidecar = _inside(self.project_root / 'Assets' / (asset_id + '.sceneops-unity.json'), self.workspace_root)
            staged.parent.mkdir(exist_ok=True)
            if staged.exists() and staged.read_bytes() != source.read_bytes():
                raise UnityAgentSessionError('UNITY_OVERWRITE_REQUIRES_APPROVAL', 'Staged asset already exists with different content.')
            if not staged.exists():
                shutil.copyfile(source, staged)
            manifest = {**manifest, 'project_id': self.workspace_root.name, 'source_file': str(staged)}
            if sidecar.exists() and json.loads(sidecar.read_text()) != manifest:
                raise UnityAgentSessionError('UNITY_OVERWRITE_REQUIRES_APPROVAL', 'Import manifest already exists with different content.')
            if not sidecar.exists():
                _write(sidecar, manifest)
            payload = ImportAssetPayload(source_asset_id=asset_id, source_asset_version_id=manifest['source_asset_version_id'],
                source_path=str(staged), destination_asset_path=f'Assets/{asset_id}.fbx',
                manifest_path=f'Assets/{asset_id}.sceneops-unity.json', destination_scene_path='Assets/SceneOpsAgent.unity',
                sceneops_id=sceneops_id, scene_instance_id='inst_' + asset_id.removeprefix('ast_')).model_dump(mode='json')
            serialized = json.dumps(payload, separators=(',', ':'))
            change = {'change_set_id': authorization['change_set_id'], 'base_version': 'agent-v1',
                'command': 'unity.asset.import', 'approval_state': 'approved',
                'target_object_ids': [asset_id, manifest['source_asset_version_id'], sceneops_id, payload['scene_instance_id']],
                'proposed_payload_json': serialized, 'previous_values': {}, 'proposed_values': payload,
                'rationale': 'Authorized dedicated workspace import', 'expected_result': 'FBX identity and dimensions readback',
                'impact_scope': str(self.project_root), 'risk': 'low', 'validation_plan': ['Read objects and console'],
                'rollback_plan': ['Retain independent project and artifacts for review']}
            batch = {'requestId': request_id, 'command': 'unity.asset.import', 'projectId': self.workspace_root.name,
                'projectRoot': str(self.project_root), 'baseVersion': 'agent-v1', 'executionMode': 'live',
                'payloadJson': serialized, 'changeSetJson': json.dumps(change)}
            replay = (self.mailbox / (request_id + '.result.json')).exists()
            result = self._exchange(request_id, 'unity.asset.import', batch=batch, authorization=authorization)
            observed = self.inspect()
            objects = [obj for obj in observed['objects'] if obj['sceneops_id'] == sceneops_id]
            if len(objects) != 1:
                raise UnityAgentSessionError('UNITY_IDENTITY_READBACK_FAILED', 'Expected exactly one imported source identity.')
            return {**result, **objects[0], 'mode': 'cached' if replay else 'live', 'readback_mode': 'live', 'status': 'succeeded', 'objects': objects,
                'errors': observed['errors'], 'scene_path': observed['scene_path'], 'session_id': state['session_id'], 'change_set': change}

    def inspect_content(self):
        from .content_session import inspect_content
        return inspect_content(self)

    def import_content(self, *, request_id, asset_id, source_version, expected_source_version, fbx_path, node_ids, instance_ids, authorization):
        from .content_session import import_content
        with self._lock:
            return import_content(self, request_id=request_id, asset_id=asset_id, source_version=source_version,
                expected_source_version=expected_source_version, fbx_path=fbx_path, node_ids=node_ids,
                instance_ids=instance_ids, authorization=authorization)

    def edit_content(self, *, request_id, instance_id, expected, authorization, position=None, interaction_distance=None, requires_key=None):
        from .content_session import edit_content
        with self._lock:
            return edit_content(self, request_id=request_id, instance_id=instance_id, expected=expected,
                position=position, interaction_distance=interaction_distance, requires_key=requires_key, authorization=authorization)

    def focus_content(self, *, request_id, instance_id, authorization):
        from .content_session import focus_content
        return focus_content(self, request_id=request_id, instance_id=instance_id, authorization=authorization)

    def save_content(self, *, request_id, reopen=False, authorization):
        from .content_session import save_content
        with self._lock:
            return save_content(self, request_id=request_id, reopen=reopen, authorization=authorization)

    def play_content(self, *, request_id, operation, input=None, authorization):
        from .content_session import play_content
        with self._lock:
            return play_content(self, request_id=request_id, operation=operation, input=input, authorization=authorization)

    def stop(self) -> None:
        self._cancel.set()
        if (self._process is None or self._process.poll() is not None) and self._owned_pid_alive():
            pid = self._config['pid']
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 10
            while self._matches_project_process(pid) and time.monotonic() < deadline:
                time.sleep(.1)
            if self._matches_project_process(pid):
                os.kill(pid, signal.SIGKILL)
                deadline = time.monotonic() + 5
                while self._matches_project_process(pid) and time.monotonic() < deadline:
                    time.sleep(.1)
                if self._matches_project_process(pid):
                    raise UnityAgentSessionError('UNITY_STOP_UNCONFIRMED', 'Dedicated Editor termination was not confirmed.')
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        if self._config:
            self._config['closed'] = True
            _write(self.mailbox / 'session.json', self._config)
