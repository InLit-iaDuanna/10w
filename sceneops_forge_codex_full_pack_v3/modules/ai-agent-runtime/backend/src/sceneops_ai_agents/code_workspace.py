"""Registered, bounded source-file operations. Model text is data, never executed."""
from contextlib import contextmanager
import difflib
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import stat
from uuid import uuid4

from sceneops_harness import HarnessError

MAX_FILE_BYTES = 65536
MAX_TASK_BYTES = 524288
SOURCE_SUFFIXES = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css', '.html',
                   '.json', '.md', '.txt', '.cs', '.glsl', '.vert', '.frag', '.wgsl'}
DENIED_NAMES = {'package-lock.json', 'npm-shrinkwrap.json', 'pnpm-lock.yaml', 'yarn.lock',
                'bun.lock', 'bun.lockb', 'sceneops-outputs.json'}
DENIED_DIRECTORIES = {'node_modules', 'Library', 'Temp', 'Obj', 'Logs', 'Build', 'Builds',
                      'dist', 'build', 'coverage', '__pycache__'}
PROJECT_DEMO_DERIVED_PATHS = {'src/game/sceneops-demo-content.ts',
                              'src/game/sceneops-test.ts'}


def source_path(value):
    path = PurePosixPath(value)
    if (not value or len(value) > 240 or '\\' in value or path.is_absolute()
            or path.as_posix() != value or any(ord(char) < 32 for char in value)
            or any(part.startswith('.') or part in DENIED_DIRECTORIES for part in path.parts)
            or path.name in DENIED_NAMES or path.suffix.lower() not in SOURCE_SUFFIXES):
        raise HarnessError('CODE_PATH_DENIED', '仅允许卡片目录内的普通源码路径；隐藏目录、依赖和生成目录不在范围内。')
    return path


def task_source_path(task, value):
    path = source_path(value)
    if (task.authorization_card.task_profile == 'project-demo-agent'
            and path.as_posix() in PROJECT_DEMO_DERIVED_PATHS):
        raise HarnessError('CODE_PATH_DERIVED',
            '该文件由 SceneOps 物化或测试适配器生成；请修改资产、场景、行为参数或独立游戏源码。')
    return path


@contextmanager
def source_parent(root, relative, *, create=False):
    """Hold directory descriptors so symbolic-link swaps cannot redirect file access."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptors = [os.open(root, flags)]
    try:
        for part in relative.parts[:-1]:
            if create:
                try:
                    os.mkdir(part, 0o755, dir_fd=descriptors[-1])
                except FileExistsError:
                    pass
            descriptors.append(os.open(part, flags, dir_fd=descriptors[-1]))
        yield descriptors[-1]
    except FileNotFoundError:
        raise
    except OSError as error:
        raise HarnessError('CODE_PATH_DENIED', '源码目录不存在、不可访问或包含链接。') from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def read_at(parent, name):
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    except FileNotFoundError:
        return None, None
    except OSError as error:
        raise HarnessError('CODE_PATH_DENIED', '源码文件不可访问或包含链接。') from error
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_FILE_BYTES:
            raise HarnessError('CODE_FILE_DENIED', '仅允许单链接、最多 64 KiB 的普通 UTF-8 源码文件。')
        content = stream.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES or b'\0' in content:
            raise HarnessError('CODE_FILE_DENIED', '文件超出大小限制或属于二进制。')
        try:
            return content.decode('utf-8'), info
        except UnicodeDecodeError as error:
            raise HarnessError('CODE_FILE_DENIED', '源码必须为 UTF-8 文本。') from error


def read_source(root, value):
    relative = source_path(value)
    try:
        with source_parent(root, relative) as parent:
            return read_at(parent, relative.name)[0]
    except FileNotFoundError:
        return None


class CodeWorkspace:
    def __init__(self, service):
        self.service = service
        with service.records.connect() as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS agent_code_writes (
                request_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, path TEXT NOT NULL,
                before_content TEXT, after_content TEXT NOT NULL, evidence TEXT NOT NULL,
                state TEXT NOT NULL)''')

    def inspect(self, task):
        root = Path(task.grant.workspace_root)
        files, visited, truncated = [], 0, False
        for parent, directories, names in os.walk(root, followlinks=False):
            directories[:] = sorted(name for name in directories if not name.startswith('.')
                and name not in DENIED_DIRECTORIES and not (Path(parent) / name).is_symlink())
            visited += 1
            if visited > 256:
                truncated = True
                break
            for name in sorted(names):
                relative = (Path(parent) / name).relative_to(root).as_posix()
                try:
                    task_source_path(task, relative)
                    with source_parent(root, PurePosixPath(relative)) as descriptor:
                        info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    if stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= MAX_FILE_BYTES:
                        files.append({'path': relative, 'size_bytes': info.st_size})
                except (HarnessError, OSError):
                    continue
                if len(files) >= 256:
                    truncated = True
                    break
            if truncated:
                break
        return {'tool': 'code', 'mode': 'live', 'project_id': task.project_id,
                'workspace_id': task.grant.workspace_id, 'card_id': task.grant.card_id,
                'branch': task.grant.branch, 'files': files, 'truncated': truncated,
                'max_file_bytes': MAX_FILE_BYTES, 'max_task_write_bytes': MAX_TASK_BYTES}

    def rows(self, task_id):
        with self.service.records.connect() as connection:
            return connection.execute('SELECT request_id,path,before_content,after_content,evidence,state '
                                      'FROM agent_code_writes WHERE task_id=? ORDER BY rowid', (task_id,)).fetchall()

    def stage(self, task, entry):
        data = entry.action.inputs
        for content in (data['expected_content'], data['content']):
            if content is not None and (len(content.encode('utf-8')) > MAX_FILE_BYTES or '\0' in content):
                raise HarnessError('CODE_FILE_DENIED', '每个源码文件最多 64 KiB，且必须为 UTF-8 文本。')
        task_source_path(task, data['path'])
        with self.service.records.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT task_id,path,before_content,after_content,evidence,state '
                'FROM agent_code_writes WHERE request_id=?', (entry.request_id,)).fetchone()
            if row:
                if row[:4] != (task.id, data['path'], data['expected_content'], data['content']):
                    raise HarnessError('REQUEST_ID_CONFLICT', '文件写入请求不能更换内容。')
                return json.loads(row[4]), row[5]
            totals = connection.execute('SELECT COUNT(*),COALESCE(SUM(LENGTH(CAST(after_content AS BLOB))),0) '
                'FROM agent_code_writes WHERE task_id=?', (task.id,)).fetchone()
            if totals[0] >= 32 or totals[1] + len(data['content'].encode('utf-8')) > MAX_TASK_BYTES:
                raise HarnessError('CODE_WRITE_BUDGET', '已达到源码写入次数或累计 512 KiB 限额。')
            evidence = {'tool': 'code', 'mode': 'live', 'path': data['path'],
                'before': data['expected_content'], 'after': data['content'],
                'diff': ''.join(difflib.unified_diff((data['expected_content'] or '').splitlines(keepends=True),
                    data['content'].splitlines(keepends=True), fromfile='before/' + data['path'], tofile='after/' + data['path'])),
                'request_id': entry.request_id, 'project_id': task.project_id,
                'workspace_id': task.grant.workspace_id,
                'card_id': task.grant.card_id, 'branch': task.grant.branch,
                'effect_state': 'STAGED'}
            connection.execute('INSERT INTO agent_code_writes VALUES(?,?,?,?,?,?,?)',
                (entry.request_id, task.id, data['path'], data['expected_content'], data['content'],
                 json.dumps(evidence, ensure_ascii=False), 'STAGED'))
            return evidence, 'NEW'

    def commit_evidence(self, request_id, evidence, *, recovered=False):
        evidence = {**evidence, 'effect_state': 'COMMITTED', 'readback': evidence['after'],
                    'content_verified': True, 'recovered': recovered}
        with self.service.records.connect() as connection:
            connection.execute("UPDATE agent_code_writes SET state='COMMITTED',evidence=? WHERE request_id=?",
                               (json.dumps(evidence, ensure_ascii=False), request_id))
        return evidence

    def write(self, task, entry):
        if not entry.change_set or not entry.approval_id:
            raise HarnessError('ACTION_APPROVAL_REQUIRED', '源码写入需要已授权的 ChangeSet。')
        if not any(row[0] == entry.request_id for row in self.rows(task.id)):
            actual = read_source(task.grant.workspace_root, entry.action.inputs['path'])
            if actual != entry.action.inputs['expected_content']:
                raise HarnessError('CODE_PREIMAGE_CONFLICT', '源码精确前文不匹配；未覆盖当前文件，请重新读取。')
            if actual == entry.action.inputs['content']:
                raise HarnessError('CODE_NO_CHANGE', '源码内容没有改变，不登记为实际写入。')
        evidence, state = self.stage(task, entry)
        root, relative = Path(task.grant.workspace_root), task_source_path(task, evidence['path'])
        with source_parent(root, relative, create=True) as parent:
            current, info = read_at(parent, relative.name)
            if state != 'NEW' and current == evidence['after']:
                committed = self.commit_evidence(entry.request_id, evidence, recovered=True)
                self.service.game.invalidate_workspace(root)
                return committed
            if state == 'COMMITTED' or current != evidence['before']:
                raise HarnessError('CODE_PREIMAGE_CONFLICT', '源码已改变，精确前文不匹配；未覆盖当前文件，请重新读取。')
            temporary = '.sceneops-write-' + uuid4().hex
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 stat.S_IMODE(info.st_mode) if info else 0o644, dir_fd=parent)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(evidence['after'].encode('utf-8'))
                    stream.flush()
                    os.fsync(stream.fileno())
                self.service.check_grant(task.id, 'code.file.write')
                # Validate the current parent identity again before publishing the replacement.
                with source_parent(root, relative) as current_parent:
                    if (os.fstat(parent).st_dev, os.fstat(parent).st_ino) != (os.fstat(current_parent).st_dev, os.fstat(current_parent).st_ino):
                        raise HarnessError('CODE_PREIMAGE_CONFLICT', '源码父目录已改变，不能发布写入。')
                latest, latest_info = read_at(parent, relative.name)
                if latest != evidence['before'] or (info is not None and
                        (latest_info is None or (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns) !=
                         (latest_info.st_dev, latest_info.st_ino, latest_info.st_mtime_ns, latest_info.st_ctime_ns))):
                    raise HarnessError('CODE_PREIMAGE_CONFLICT', '源码在写入准备期间改变，未覆盖。')
                if info is None:
                    os.link(temporary, relative.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                    os.unlink(temporary, dir_fd=parent)
                    temporary = None
                else:
                    # An advisory inode lock coordinates cooperating source writers.
                    original = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
                    try:
                        fcntl.flock(original, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        if read_at(parent, relative.name)[0] != evidence['before']:
                            raise HarnessError('CODE_PREIMAGE_CONFLICT', '源码前文已改变，未覆盖。')
                        os.replace(temporary, relative.name, src_dir_fd=parent, dst_dir_fd=parent)
                        temporary = None
                    finally:
                        os.close(original)
                os.fsync(parent)
                if read_at(parent, relative.name)[0] != evidence['after']:
                    raise HarnessError('ACTION_UNCERTAIN', '写入后源码发生变化，需要检查当前文件。')
                committed = self.commit_evidence(entry.request_id, evidence)
                self.service.game.invalidate_workspace(root)
                return committed
            finally:
                if temporary is not None:
                    os.unlink(temporary, dir_fd=parent)

    def reconcile(self, task, entry):
        """Read first after an uncertain delivery. Never write or replay during recovery."""
        row = next((row for row in self.rows(task.id) if row[0] == entry.request_id), None)
        if row is None:
            return 'NONE', None
        try:
            if task.authorization_card.task_profile in ('project-demo', 'project-demo-agent'):
                self.service.project_demo_workspace(task.project_id, task.grant.workspace_id,
                    expected_root=task.grant.workspace_root)
            else:
                self.service.card_workspace(task.project_id, task.grant.card_id,
                    expected_root=task.grant.workspace_root, expected_branch=task.grant.branch)
            current = read_source(task.grant.workspace_root, row[1])
        except FileNotFoundError:
            current = None
        except (HarnessError, OSError):
            return 'UNKNOWN', None
        if current == row[3]:
            return 'COMMITTED', self.commit_evidence(entry.request_id, json.loads(row[4]), recovered=True)
        if current == row[2] and row[5] == 'STAGED':
            return 'NONE', None
        return 'UNKNOWN', None

    def finish(self, task):
        writes = [entry for entry in task.actions if entry.action.capability_id == 'code.file.write'
                  and entry.state == 'succeeded' and entry.effect_state == 'COMMITTED']
        if not writes:
            raise HarnessError('VERIFICATION_INCOMPLETE', '此任务还没有实际写入并回读的源码。')
        latest = {entry.action.inputs['path']: entry.action.inputs['content'] for entry in writes}
        for path, content in latest.items():
            if read_source(task.grant.workspace_root, path) != content:
                raise HarnessError('CODE_READBACK_CONFLICT', '当前源码与已登记写入不同，需检查后继续。')
        return {'tool': 'code', 'mode': 'live', 'delivery_status': 'code_written',
                'content_verified': True, 'verified': False, 'gameplay_verified': False,
                'compilation_verified': False, 'changed_files': sorted(latest),
                'project_id': task.project_id, 'workspace_id': task.grant.workspace_id,
                'card_id': task.grant.card_id, 'branch': task.grant.branch,
                'summary': '源码已写入并回读，待检查；未运行或编译。'}
