"""Bounded Git operations for application-bound folder projects."""
import json
import os
from pathlib import Path
import re
import subprocess
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone


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
        self.initialize_root(root)
        return {"root_path": str(root), "branch": self._branch(root),
                "head_commit": self._git(root, "rev-parse", "--verify", "HEAD", optional=True)}

    def repair_moved_worktrees(self, project_id, moved_root):
        """Repair Git's absolute linked-worktree pointers before publishing a moved root."""
        with self.repository.connect() as connection:
            rows = connection.execute(
                "SELECT card_id,branch,worktree_path FROM workspace_card_worktrees WHERE project_id=?",
                (project_id,),
            ).fetchall()
        if not rows:
            return
        targets = [Path(row["worktree_path"]) for row in rows]
        if any(not target.is_dir() or target.is_symlink() for target in targets):
            raise GitProjectError("已有卡片工作区不可读取，不能完成项目移动。")
        self._git(moved_root, "worktree", "repair", *(str(target) for target in targets))
        for row, target in zip(rows, targets):
            self._verify_worktree(moved_root, target, row["branch"])

    @classmethod
    def initialize_root(cls, root):
        metadata = root / ".git"
        if metadata.is_symlink() or (metadata.exists() and not metadata.is_dir()):
            raise GitProjectError("项目必须使用独立 Git 仓库，不能绑定其他仓库的工作区。")
        if not metadata.exists():
            cls._git(root, "init", "--initial-branch=codex/integration", "--template=")
        cls.verify_root_path(root)
        if cls._branch(root) != "codex/integration":
            raise GitProjectError("新项目必须初始化在 codex/integration 分支。")

    def _verify_root(self, root):
        self.verify_root_path(root)

    @classmethod
    def verify_root_path(cls, root):
        if not (root / ".git").is_dir() or (root / ".git").is_symlink():
            raise GitProjectError("请先明确启用此项目的 Git 版本管理。")
        actual = cls._git(root, "rev-parse", "--show-toplevel")
        if Path(actual).resolve() != root.resolve():
            raise GitProjectError("Git 根目录与绑定项目不一致。")

    @classmethod
    def _branch(cls, root):
        branch = cls._git(root, "symbolic-ref", "--quiet", "HEAD", optional=True)
        if not branch or not branch.startswith("refs/heads/"):
            raise GitProjectError("项目处于游离版本，请切回项目分支后重试。")
        return branch.removeprefix("refs/heads/")

    def game_baseline(self, project_id):
        with self.repository.connect() as connection:
            row = connection.execute("SELECT * FROM workspace_game_baselines WHERE project_id=?",
                                     (project_id,)).fetchone()
        return dict(row) if row else None

    def commit_game_baseline(self, project_id, paths, message, design_version, architecture_version=1):
        root = self._root(project_id)
        self._verify_root(root)
        if self.repository.get_folder_project(project_id).project_kind != "sceneops_created":
            raise GitProjectError("只有 SceneOps 新建工程可以自动建立游戏代码基线。")
        if self._branch(root) != "codex/integration":
            raise GitProjectError("工程基线只能提交到 codex/integration。")
        if self._git_operation_active(root):
            raise GitProjectError("Git 正在合并、变基或解决冲突，不能建立工程基线。")
        head = self._git(root, "rev-parse", "--verify", "HEAD", optional=True)
        design = self._git(root, "rev-parse", "--verify", f"refs/tags/v{design_version}^{{commit}}", optional=True)
        if not head or not design or self._git(root, "merge-base", "--is-ancestor", design, head, optional=True) is None:
            raise GitProjectError("当前集成分支没有包含已登记的正式策划版本。")
        relative_paths = sorted(set(paths))
        if not relative_paths or any(Path(path).is_absolute() or ".." in Path(path).parts for path in relative_paths):
            raise GitProjectError("工程基线路径无效。")
        with self._locked_index(root) as index_state, self.repository.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM workspace_game_baselines WHERE project_id=?",
                                     (project_id,)).fetchone()
            if row is not None:
                if row["design_version"] != design_version or row["architecture_version"] != architecture_version:
                    raise GitProjectError("已登记的工程基线与当前技术方案不一致。")
                commit = row["commit_id"]
                if self._git(root, "rev-parse", "--verify", commit + "^{commit}", optional=True) != commit:
                    raise GitProjectError("已登记的工程基线提交不存在。")
                if not row["index_synced"]:
                    parent = self._git(root, "rev-parse", "--verify", commit + "^", optional=True)
                    current = self._git(root, "rev-parse", "--verify", "HEAD", optional=True)
                    if current == parent:
                        self._git(root, "update-ref", "refs/heads/codex/integration", commit, parent)
                    elif current != commit:
                        raise GitProjectError("工程基线恢复期间集成分支已经变化，请人工检查。")
                    self._sync_paths_from_commit(root, index_state, relative_paths, commit, parent)
                    self._finish_baseline_index(connection, index_state, project_id)
                return commit
            blobs = {}
            for relative in relative_paths:
                source = root / relative
                if source.is_symlink() or not source.is_file():
                    raise GitProjectError(f"工程基线文件 {relative} 不存在或不是普通文件。")
                try:
                    content = source.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as error:
                    raise GitProjectError(f"工程基线文件 {relative} 无法读取。") from error
                blob = self._git(root, "hash-object", "-w", "--stdin", input=content)
                blobs[relative] = blob
                self._prepare_index_entry(root, index_state, relative, blob, head)
            with tempfile.TemporaryDirectory(prefix="sceneops-baseline-index-") as directory:
                baseline_index = Path(directory) / "index"
                env = {"GIT_INDEX_FILE": str(baseline_index)}
                self._git(root, "read-tree", head, environment=env)
                for relative in relative_paths:
                    self._git(root, "update-index", "--add", "--cacheinfo", "100644", blobs[relative],
                              relative, environment=env)
                tree = self._git(root, "write-tree", environment=env)
            commit = self._git(root, "commit-tree", tree, "-p", head, "-m", message)
            connection.execute("""INSERT INTO workspace_game_baselines
                (project_id,architecture_version,design_version,commit_id,index_synced,created_at)
                VALUES (?,?,?,?,0,?)""",
                (project_id, architecture_version, design_version, commit,
                 datetime.now(timezone.utc).isoformat()))
            connection.commit()
            self._git(root, "update-ref", "refs/heads/codex/integration", commit, head)
            connection.execute("BEGIN IMMEDIATE")
            self._finish_baseline_index(connection, index_state, project_id)
            return commit

    def _sync_paths_from_commit(self, root, index_state, paths, commit, parent):
        for relative in paths:
            entry = self._git(root, "ls-tree", commit, "--", relative)
            fields = entry.split("\t", 1)[0].split() if entry else []
            if len(fields) != 3 or fields[1] != "blob":
                raise GitProjectError(f"工程基线提交缺少 {relative}。")
            self._prepare_index_entry(root, index_state, relative, fields[2], parent)

    @staticmethod
    def _finish_baseline_index(connection, state, project_id):
        os.replace(state["lock"], state["index"])
        state["published"] = True
        connection.execute("UPDATE workspace_game_baselines SET index_synced=1 WHERE project_id=?",
                           (project_id,))

    def _git_operation_active(self, root):
        if self._git(root, "ls-files", "-u"):
            return True
        return any(self._git(root, "rev-parse", "--verify", ref, optional=True) is not None
                   for ref in ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD"))

    def _prepare_index_entry(self, root, state, relative, blob, head):
        env = {"GIT_INDEX_FILE": str(state["lock"])}
        staged = self._git(root, "ls-files", "--stage", "--", relative, environment=env)
        entries = staged.splitlines() if staged else []
        current = None
        if entries:
            fields = entries[0].split("\t", 1)[0].split()
            if len(entries) != 1 or fields[2] != "0":
                raise GitProjectError(f"工程基线文件 {relative} 存在未解决的暂存冲突。")
            current = (fields[0], fields[1])
        previous = self._git(root, "ls-tree", head, "--", relative) if head else ""
        previous_fields = previous.split("\t", 1)[0].split() if previous else []
        expected = (previous_fields[0], previous_fields[2]) if previous_fields else None
        if current not in (expected, ("100644", blob)):
            raise GitProjectError(f"工程基线文件 {relative} 已有不同的暂存修改。")
        self._git(root, "update-index", "--add", "--cacheinfo", "100644", blob, relative, environment=env)

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

    def restore_design_state(self, project_id, versions, card_branches, baseline=None):
        """Re-register project-owned Git state only after its repository proves every claim."""
        root = self._root(project_id)
        with self.repository.connect() as connection:
            registered_versions = {row["version"]: row for row in connection.execute(
                "SELECT * FROM workspace_git_versions WHERE project_id=?", (project_id,))}
            registered_branches = {row["card_id"]: row for row in connection.execute(
                "SELECT * FROM workspace_card_worktrees WHERE project_id=?", (project_id,))}
            registered_baseline = connection.execute(
                "SELECT * FROM workspace_game_baselines WHERE project_id=?", (project_id,)).fetchone()
        versions_ready = all(item.get("number") in registered_versions and
            registered_versions[item["number"]]["commit_id"] == item.get("commit") and
            registered_versions[item["number"]]["index_synced"] for item in versions)
        branches_ready = all(item.get("card_id") in registered_branches and
            all(registered_branches[item["card_id"]][key] == item.get(key)
                for key in ("branch", "worktree_path", "base_commit")) for item in card_branches)
        baseline_ready = baseline is None or (registered_baseline is not None and
            registered_baseline["architecture_version"] == baseline.get("architecture_version") and
            registered_baseline["design_version"] == baseline.get("design_version") and
            registered_baseline["commit_id"] == baseline.get("commit") and
            registered_baseline["index_synced"])
        if versions_ready and branches_ready and baseline_ready:
            return
        self._verify_root(root)
        head = self._git(root, "rev-parse", "--verify", "HEAD", optional=True)
        verified_versions = {}
        for item in versions:
            version, commit, tag = item.get("number"), item.get("commit"), item.get("tag")
            if (isinstance(version, bool) or not isinstance(version, int) or version < 1 or
                    tag != f"v{version}" or not isinstance(commit, str)):
                raise GitProjectError("项目内版本登记格式无效，不能恢复。")
            tagged = self._git(root, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}", optional=True)
            if tagged != commit or not head or self._git(root, "merge-base", "--is-ancestor",
                    commit, head, optional=True) is None:
                raise GitProjectError(f"项目内版本 {tag} 与当前 Git 历史不一致，不能恢复。")
            relative = f".sceneops/design/snapshots/{tag}.json"
            self._verify_snapshot(root, commit, relative, item.get("payload"))
            verified_versions[version] = commit

        baseline_row = None
        if baseline is not None:
            architecture_version = baseline.get("architecture_version")
            design_version = baseline.get("design_version")
            commit = baseline.get("commit")
            if (isinstance(architecture_version, bool) or not isinstance(architecture_version, int) or
                    isinstance(design_version, bool) or not isinstance(design_version, int) or
                    not isinstance(commit, str) or design_version not in verified_versions):
                raise GitProjectError("项目内工程基线登记格式无效，不能恢复。")
            resolved = self._git(root, "rev-parse", "--verify", commit + "^{commit}", optional=True)
            design_commit = verified_versions[design_version]
            if (resolved != commit or self._git(root, "merge-base", "--is-ancestor",
                    design_commit, commit, optional=True) is None or self._git(root, "merge-base",
                    "--is-ancestor", commit, head, optional=True) is None):
                raise GitProjectError("项目内工程基线与当前 Git 历史不一致，不能恢复。")
            architecture = self._git(root, "show", f"{commit}:.sceneops/game-architecture.json", optional=True)
            try:
                marker = json.loads(architecture) if architecture is not None else None
            except json.JSONDecodeError:
                marker = None
            if not isinstance(marker, dict) or marker.get("architecture_version") != architecture_version or marker.get("design_version") != design_version:
                raise GitProjectError("项目内工程基线与架构记录不一致，不能恢复。")
            baseline_row = (project_id, architecture_version, design_version, commit, 1,
                            baseline.get("created_at") or datetime.now(timezone.utc).isoformat())

        branch_rows = []
        for item in card_branches:
            card_id, branch = item.get("card_id"), item.get("branch")
            base_commit, raw_path = item.get("base_commit"), item.get("worktree_path")
            if (not isinstance(card_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", card_id)
                    or branch != f"codex/card-{card_id}" or not isinstance(base_commit, str)
                    or not isinstance(raw_path, str)):
                raise GitProjectError("项目内卡片分支登记格式无效，不能恢复。")
            target = Path(raw_path)
            self._verify_restored_worktree_path(root, target, project_id, card_id, branch)
            branch_head = self._git(root, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}", optional=True)
            base = self._git(root, "rev-parse", "--verify", base_commit + "^{commit}", optional=True)
            latest_version = verified_versions[max(verified_versions)] if verified_versions else None
            required_base = baseline_row[3] if baseline_row else latest_version
            if (base != base_commit or not branch_head or self._git(root, "merge-base", "--is-ancestor",
                    base_commit, branch_head, optional=True) is None or (required_base and self._git(root,
                    "merge-base", "--is-ancestor", required_base, base_commit, optional=True) is None)):
                raise GitProjectError(f"卡片 {card_id} 的分支历史不一致，不能恢复。")
            brief = self._read_card_brief(target)
            if (brief.get("project_id") != project_id or brief.get("card_id") != card_id or
                    brief.get("base_commit") != base_commit):
                raise GitProjectError(f"卡片 {card_id} 的说明与工作区不一致，不能恢复。")
            branch_rows.append((project_id, card_id, branch, str(target), base_commit))

        with self.repository.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for item in versions:
                existing = connection.execute("SELECT commit_id FROM workspace_git_versions WHERE project_id=? AND version=?",
                                              (project_id, item["number"])).fetchone()
                if existing and existing["commit_id"] != item["commit"]:
                    raise GitProjectError("本机已有不同的设计版本登记，不能覆盖。")
                connection.execute("""INSERT INTO workspace_git_versions
                    (project_id,version,commit_id,index_synced) VALUES (?,?,?,1)
                    ON CONFLICT(project_id,version) DO UPDATE SET
                    commit_id=excluded.commit_id,index_synced=1
                    WHERE workspace_git_versions.commit_id=excluded.commit_id""",
                    (project_id, item["number"], item["commit"]))
            if baseline_row:
                existing = connection.execute("SELECT * FROM workspace_game_baselines WHERE project_id=?",
                                              (project_id,)).fetchone()
                if existing and (existing["architecture_version"], existing["design_version"], existing["commit_id"]) != baseline_row[1:4]:
                    raise GitProjectError("本机已有不同的工程基线登记，不能覆盖。")
                connection.execute("INSERT OR IGNORE INTO workspace_game_baselines VALUES (?,?,?,?,?,?)", baseline_row)
            for row in branch_rows:
                existing = connection.execute("SELECT * FROM workspace_card_worktrees WHERE project_id=? AND card_id=?",
                                              row[:2]).fetchone()
                if existing and tuple(existing[key] for key in ("project_id", "card_id", "branch", "worktree_path", "base_commit")) != row:
                    raise GitProjectError("本机已有不同的卡片工作区登记，不能覆盖。")
                connection.execute("INSERT OR IGNORE INTO workspace_card_worktrees VALUES (?,?,?,?,?)", row)

    def _verify_restored_worktree_path(self, root, target, project_id, card_id, branch):
        if (target.name != card_id or target.parent.name != project_id or
                target.parent.parent.name != "card-worktrees" or target.resolve().is_relative_to(root.resolve())):
            raise GitProjectError("项目内卡片工作区路径无效，不能恢复。")
        self._verify_worktree(root, target, branch)

    def _read_card_brief(self, target):
        brief = target / ".sceneops" / "card-brief.json"
        try:
            descriptor = os.open(brief, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                raw = stream.read(65537)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or len(raw) > 65536:
                raise GitProjectError("卡片说明必须为有界普通文件。")
            context = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GitProjectError("卡片说明不可读取，不能恢复工作区。") from error
        if not isinstance(context, dict):
            raise GitProjectError("卡片说明格式无效，不能恢复工作区。")
        return context

    def open_card(self, project_id, card_id, title, card=None):
        if not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value)
                   for value in (project_id, card_id)):
            raise GitProjectError("项目或卡片标识无效。")
        root = self._root(project_id)
        self._verify_root(root)
        with self.repository.connect() as connection:
            version = connection.execute("SELECT version, commit_id FROM workspace_git_versions WHERE project_id=? AND index_synced=1 ORDER BY version DESC LIMIT 1",
                                         (project_id,)).fetchone()
            registered = connection.execute("SELECT * FROM workspace_card_worktrees WHERE project_id=? AND card_id=?",
                                            (project_id, card_id)).fetchone()
            baseline = connection.execute("SELECT * FROM workspace_game_baselines WHERE project_id=?",
                                          (project_id,)).fetchone()
        if registered is not None:
            head = registered["base_commit"]
        else:
            if self._branch(root) != "codex/integration":
                raise GitProjectError("新卡片只能从 codex/integration 的当前版本创建。")
            if self._git_operation_active(root):
                raise GitProjectError("Git 正在合并、变基或解决冲突，不能创建卡片工作区。")
            head = self._git(root, "rev-parse", "--verify", "HEAD", optional=True)
            confirmed = version and self._git(root, "rev-parse", "--verify",
                f"refs/tags/v{version['version']}^{{commit}}", optional=True) == version["commit_id"]
            if not head or not confirmed or self._git(root, "merge-base", "--is-ancestor", version["commit_id"], head, optional=True) is None:
                raise GitProjectError("请先确认正式策划版本，再打开卡片工作区。")
            if baseline is not None:
                if not baseline["index_synced"] or self._git(root, "merge-base", "--is-ancestor",
                        baseline["commit_id"], head, optional=True) is None:
                    raise GitProjectError("当前集成分支没有包含已登记的游戏工程基线。")
            elif self._has_game_architecture(root):
                raise GitProjectError("此项目没有可验证的游戏工程基线；已有工程采用流程尚未完成。")
            self._require_clean_project_sources(root)
        branch = f"codex/card-{card_id}"
        base = self.repository.path.absolute().parent / "card-worktrees"
        target = Path(registered["worktree_path"]) if registered is not None else base / project_id / card_id
        if registered is None:
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

    @staticmethod
    def _has_game_architecture(root):
        marker = root / ".sceneops" / "game-architecture.json"
        return marker.exists() or marker.is_symlink()

    def _require_clean_project_sources(self, root):
        paths = [".gitignore", ".sceneops/project.json", ".sceneops/game-architecture.json",
                 "README.md", "ARCHITECTURE.md", "package.json", "tsconfig.json", "index.html", "src"]
        dirty = self._git(root, "status", "--porcelain=v1", "--untracked-files=all", "--", *paths)
        if dirty:
            raise GitProjectError("主工程仍有未提交的源码或工程配置，不能创建卡片工作区。")

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
        expected = Path(row["worktree_path"])
        if row["branch"] != f"codex/card-{card_id}":
            raise GitProjectError("卡片工作区登记与实际目录不一致。")
        self._verify_restored_worktree_path(root, expected, project_id, card_id, row["branch"])
        self.repository._safe_existing_directory(expected / '.sceneops')
        context = self._read_card_brief(expected)
        if not isinstance(context, dict) or context.get('project_id') != project_id or context.get('card_id') != card_id:
            raise GitProjectError('已登记卡片说明与当前项目或卡片不一致。')
        return {**dict(row), 'card_brief': context}
