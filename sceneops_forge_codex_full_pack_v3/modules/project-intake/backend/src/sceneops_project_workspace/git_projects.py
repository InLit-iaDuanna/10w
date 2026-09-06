"""Bounded Git operations for application-bound folder projects."""
import json
import os
from pathlib import Path
import re
import subprocess
import stat
import tempfile
from contextlib import contextmanager


class GitProjectError(ValueError):
    pass


class GitProjects:
    def __init__(self, repository):
        self.repository = repository

    def _root(self, project_id):
        return Path(self.repository.get_folder_project(project_id).root_path)

    @staticmethod
    def _git(root, *arguments, input=None, environment=None, optional=False):
        # Git environment inherited from a developer shell must never redirect writes.
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull})
        env.update(environment or {})
        command = ["git", "-c", "core.hooksPath=" + os.devnull,
                   "-c", "core.fsmonitor=false",
                   "-c", "commit.gpgSign=false", "-c", "tag.gpgSign=false",
                   "-c", "user.name=SceneOps", "-c", "user.email=sceneops@localhost",
                   "-C", str(root), *arguments]
        try:
            result = subprocess.run(command, input=input, text=True, capture_output=True,
                                    env=env, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise GitProjectError("Git 操作不可用或超时，请检查后重试。") from error
        if result.returncode and not optional:
            raise GitProjectError("Git 操作失败；已有文件和历史已保留，请检查仓库状态后重试。")
        return result.stdout.strip() if result.returncode == 0 else None

    def ensure(self, project_id):
        root = self._root(project_id)
        metadata = root / ".git"
        if metadata.is_symlink() or (metadata.exists() and not metadata.is_dir()):
            raise GitProjectError("项目必须使用独立 Git 仓库，不能绑定其他仓库的工作区。")
        if not metadata.exists():
            self._git(root, "init", "--initial-branch=codex/integration", "--template=")
        self._verify_root(root)
        return {"root_path": str(root), "branch": self._branch(root),
                "head_commit": self._git(root, "rev-parse", "--verify", "HEAD", optional=True)}

    def _verify_root(self, root):
        if not (root / ".git").is_dir() or (root / ".git").is_symlink():
            raise GitProjectError("请先明确启用此项目的 Git 版本管理。")
        actual = self._git(root, "rev-parse", "--show-toplevel")
        if Path(actual).resolve() != root.resolve():
            raise GitProjectError("Git 根目录与绑定项目不一致。")

    def _branch(self, root):
        branch = self._git(root, "symbolic-ref", "--quiet", "HEAD", optional=True)
        if not branch or not branch.startswith("refs/heads/"):
            raise GitProjectError("项目处于游离版本，请切回项目分支后重试。")
        return branch.removeprefix("refs/heads/")

    def commit_version(self, project_id, version, payload):
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise GitProjectError("设计版本必须是正整数。")
        root = self._root(project_id)
        self._verify_root(root)
        snapshot = self.repository.create_design_snapshot(project_id, payload, version)
        relative = Path(snapshot.path).relative_to(root).as_posix()
        tag = f"v{version}"
        with self._locked_index(root) as index_state, self.repository.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            record = connection.execute("SELECT commit_id, index_synced FROM workspace_git_versions WHERE project_id=? AND version=?",
                                        (project_id, version)).fetchone()
            existing = self._git(root, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}", optional=True)
            if existing:
                if record is None or record["commit_id"] != existing:
                    raise GitProjectError("此版本标签不是应用登记的版本，不能自动接管。")
                self._verify_snapshot(root, existing, relative, payload)
                if not record["index_synced"]:
                    current_head = self._git(root, "rev-parse", "--verify", "HEAD", optional=True)
                    if current_head != existing:
                        raise GitProjectError("待恢复版本之后分支已改变，请检查暂存区后重试。")
                    parent = self._git(root, "rev-parse", "--verify", existing + "^", optional=True)
                    blob = self._git(root, "rev-parse", existing + ":" + relative)
                    self._prepare_snapshot_index(root, index_state, relative, blob, parent)
                    self._finish_index(connection, index_state, project_id, version)
                return {"commit": existing, "tag": tag}
            branch = "refs/heads/" + self._branch(root)
            head = self._git(root, "rev-parse", "--verify", "HEAD", optional=True)
            with tempfile.TemporaryDirectory(prefix="sceneops-git-index-") as directory:
                env = {"GIT_INDEX_FILE": str(Path(directory) / "index")}
                self._git(root, "read-tree", head or "--empty", environment=env)
                encoded = Path(snapshot.path).read_text(encoding="utf-8")
                blob = self._git(root, "hash-object", "-w", "--stdin", input=encoded)
                self._prepare_snapshot_index(root, index_state, relative, blob, head)
                self._git(root, "update-index", "--add", "--cacheinfo", "100644", blob, relative, environment=env)
                tree = self._git(root, "write-tree", environment=env)
                parents = ["-p", head] if head else []
                commit = self._git(root, "commit-tree", tree, *parents, "-m", f"Confirm design {tag}")
            connection.execute("INSERT INTO workspace_git_versions (project_id, version, commit_id, index_synced) VALUES (?, ?, ?, 0) ON CONFLICT(project_id, version) DO UPDATE SET commit_id=excluded.commit_id, index_synced=0",
                               (project_id, version, commit))
            connection.commit()
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT commit_id FROM workspace_git_versions WHERE project_id=? AND version=?",
                                         (project_id, version)).fetchone()
            if current["commit_id"] != commit:
                raise GitProjectError("同一版本正在另一请求中确认，请重试。")
            # Publish the branch and immutable version together; concurrent edits fail atomically.
            operation = f"update {branch} {commit} {head}\n" if head else f"create {branch} {commit}\n"
            self._git(root, "update-ref", "--stdin", input="start\n" + operation +
                      f"create refs/tags/{tag} {commit}\nprepare\ncommit\n")
            self._finish_index(connection, index_state, project_id, version)
            return {"commit": commit, "tag": tag}

    @contextmanager
    def _locked_index(self, root):
        index = root / ".git" / "index"
        lock = index.with_name("index.lock")
        if index.is_symlink():
            raise GitProjectError("项目暂存区路径不安全。")
        try:
            descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            raise GitProjectError("Git 暂存区正被其他操作使用，请稍后重试。") from error
        state = {"index": index, "lock": lock, "published": False}
        try:
            with os.fdopen(descriptor, "wb") as stream:
                if index.exists():
                    stream.write(index.read_bytes())
            if not index.exists():
                with tempfile.TemporaryDirectory(prefix="sceneops-empty-index-") as directory:
                    empty = Path(directory) / "index"
                    self._git(root, "read-tree", "--empty", environment={"GIT_INDEX_FILE": str(empty)})
                    lock.write_bytes(empty.read_bytes())
            yield state
        finally:
            if not state["published"]:
                lock.unlink(missing_ok=True)

    def _prepare_snapshot_index(self, root, state, relative, blob, head):
        env = {"GIT_INDEX_FILE": str(state["lock"])}
        staged = self._git(root, "ls-files", "--stage", "--", relative, environment=env)
        entries = staged.splitlines() if staged else []
        current = None
        if entries:
            fields = entries[0].split("\t", 1)[0].split()
            if len(entries) != 1 or fields[2] != "0":
                raise GitProjectError("设计快照存在未解决的暂存冲突。")
            current = (fields[0], fields[1])
        previous = self._git(root, "ls-tree", head, "--", relative) if head else ""
        previous_fields = previous.split("\t", 1)[0].split() if previous else []
        expected = (previous_fields[0], previous_fields[2]) if previous_fields else None
        if current not in (expected, ("100644", blob)):
            raise GitProjectError("设计快照已有不同的暂存修改，请先处理后再确认版本。")
        self._git(root, "update-index", "--add", "--cacheinfo", "100644", blob, relative, environment=env)

    @staticmethod
    def _finish_index(connection, state, project_id, version):
        os.replace(state["lock"], state["index"])
        state["published"] = True
        connection.execute("UPDATE workspace_git_versions SET index_synced=1 WHERE project_id=? AND version=?",
                           (project_id, version))

    def _verify_snapshot(self, root, commit, relative, payload):
        content = self._git(root, "show", f"{commit}:{relative}", optional=True)
        try:
            matches = content is not None and json.loads(content) == payload
        except json.JSONDecodeError:
            matches = False
        if not matches:
            raise GitProjectError("此 Git 版本标签已存在且内容不同，不能覆盖。")

    def open_card(self, project_id, card_id, title, card=None):
        if not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value)
                   for value in (project_id, card_id)):
            raise GitProjectError("项目或卡片标识无效。")
        root = self._root(project_id)
        self._verify_root(root)
        head = self._git(root, "rev-parse", "--verify", "HEAD", optional=True)
        with self.repository.connect() as connection:
            version = connection.execute("SELECT version, commit_id FROM workspace_git_versions WHERE project_id=? AND index_synced=1 ORDER BY version DESC LIMIT 1",
                                         (project_id,)).fetchone()
        confirmed = version and self._git(root, "rev-parse", "--verify",
            f"refs/tags/v{version['version']}^{{commit}}", optional=True) == version["commit_id"]
        if not head or not confirmed:
            raise GitProjectError("请先确认正式策划版本，再打开卡片工作区。")
        branch = f"codex/card-{card_id}"
        base = self.repository.path.absolute().parent / "card-worktrees"
        base.mkdir(mode=0o700, exist_ok=True)
        self.repository._safe_existing_directory(base)
        parent = self.repository._real_directory(base / project_id, create=True)
        target = parent / card_id
        if target.resolve().is_relative_to(root.resolve()):
            raise GitProjectError("卡片工作区必须位于项目根目录之外。")
        with self.repository.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM workspace_card_worktrees WHERE project_id=? AND card_id=?",
                                     (project_id, card_id)).fetchone()
            if row is None:
                if target.exists() or target.is_symlink() or self._git(root, "show-ref", "--verify", f"refs/heads/{branch}", optional=True):
                    raise GitProjectError("卡片分支或目录已被占用，不能覆盖。")
                connection.execute("INSERT INTO workspace_card_worktrees VALUES (?, ?, ?, ?, ?)",
                                   (project_id, card_id, branch, str(target), head))
                connection.commit()
                connection.execute("BEGIN IMMEDIATE")
            else:
                if row["branch"] != branch or row["worktree_path"] != str(target):
                    raise GitProjectError("卡片工作区登记与当前路径不一致。")
                head = row["base_commit"]
            if target.exists() or target.is_symlink():
                self._verify_worktree(root, target, branch)
            else:
                existing = self._git(root, "rev-parse", "--verify", f"refs/heads/{branch}", optional=True)
                if existing and existing != head:
                    raise GitProjectError("未完成的卡片分支已发生变化，请检查后重试。")
                arguments = [] if existing else ["-b", branch]
                filters = self._git(root, "config", "--name-only", "--get-regexp", r"^filter\.", optional=True)
                overrides = []
                for name in {key.rsplit(".", 1)[0] for key in (filters or "").splitlines()}:
                    for setting in ("process=", "clean=", "smudge=", "required=false"):
                        overrides.extend(["-c", name + "." + setting])
                self._git(root, *overrides, "worktree", "add", *arguments, str(target), branch if existing else head)
                self._verify_worktree(root, target, branch)
            metadata = self.repository._real_directory(target / ".sceneops", create=True)
            brief = metadata / "card-brief.json"
            if not brief.exists() and not brief.is_symlink():
                self.repository._write_json_exclusive(brief, {"project_id": project_id,
                    "card_id": card_id, "title": title, "base_commit": head, "card": card})
        return {"branch": branch, "worktree_path": str(target), "base_commit": head}

    def _verify_worktree(self, root, target, branch):
        self.repository._safe_existing_directory(target)
        actual = self._git(target, "rev-parse", "--show-toplevel")
        common = self._git(target, "rev-parse", "--path-format=absolute", "--git-common-dir")
        expected = self._git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if Path(actual).resolve() != target.resolve() or common != expected or self._branch(target) != branch:
            raise GitProjectError("已有卡片目录不是登记的 Git 工作区，不能复用。")

    def get_card(self, project_id, card_id):
        """Read and verify an existing registration; never create a branch or directory."""
        root = self._root(project_id)
        self._verify_root(root)
        with self.repository.connect() as connection:
            row = connection.execute("SELECT * FROM workspace_card_worktrees WHERE project_id=? AND card_id=?",
                                     (project_id, card_id)).fetchone()
        if row is None:
            raise GitProjectError("卡片工作区尚未登记，请先打开该卡片分支。")
        expected = self.repository.path.absolute().parent / "card-worktrees" / project_id / card_id
        if row["worktree_path"] != str(expected) or row["branch"] != f"codex/card-{card_id}":
            raise GitProjectError("卡片工作区登记与实际目录不一致。")
        self._verify_worktree(root, expected, row["branch"])
        metadata = expected / '.sceneops'
        self.repository._safe_existing_directory(metadata)
        brief = metadata / 'card-brief.json'
        try:
            descriptor = os.open(brief, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65536:
                    raise GitProjectError('卡片说明必须为有界普通文件。')
                raw = stream.read(65537)
                if len(raw) > 65536:
                    raise GitProjectError('卡片说明超过读取限制。')
                context = json.loads(raw.decode('utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GitProjectError('已登记卡片说明不可读取，请检查卡片工作区。') from error
        if not isinstance(context, dict) or context.get('project_id') != project_id or context.get('card_id') != card_id:
            raise GitProjectError('已登记卡片说明与当前项目或卡片不一致。')
        return {**dict(row), 'card_brief': context}
