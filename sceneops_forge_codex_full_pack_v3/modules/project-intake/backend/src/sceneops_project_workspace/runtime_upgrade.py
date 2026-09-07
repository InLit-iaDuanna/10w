"""Versioned, three-way upgrade of generated game consumers to the GLB runtime.

The ancestor is revision 514648b and the target is revision abb0f41. Git merge-file retains
independent user edits and exposes overlapping edits as conflicts, without guessing
whether a substring means that a user's implementation is compatible.
"""
import json
import subprocess
import tempfile
from pathlib import Path

from .game_projects import GameProjectError, GameProjects

MIGRATION_VERSION = "demo-glb-runtime-1"


def _read(root: Path, relative: str) -> str:
    target = root
    for component in Path(relative).parts:
        target = target / component
        if target.is_symlink():
            raise GameProjectError(f"运行代码路径 {relative} 不允许符号链接。")
    if not target.is_file():
        raise GameProjectError(f"运行代码文件 {relative} 不存在。")
    return target.read_text(encoding="utf-8")


def _merge(current: str, ancestor: str, proposed: str) -> tuple[str, bool]:
    with tempfile.TemporaryDirectory(prefix="sceneops-runtime-merge-") as directory:
        paths = [Path(directory) / name for name in ("current", "ancestor", "proposed")]
        for path, content in zip(paths, (current, ancestor, proposed)):
            path.write_text(content, encoding="utf-8")
        result = subprocess.run(["git", "merge-file", "-p", "-L", "current", "-L", "ancestor",
                                 "-L", "proposed", *map(str, paths)],
                                capture_output=True, text=True, timeout=10)
        if result.returncode < 0 or result.returncode > 127:
            raise GameProjectError("运行代码三方合并未能完成。")
        return result.stdout, result.returncode != 0


class DemoRuntimeUpgrade:
    def __init__(self, repository):
        self.repository = repository

    def preview(self, project_id: str, workspace_id: str) -> dict:
        workspace = self.repository.get_project_demo_workspace(project_id, workspace_id)
        root = self.repository._safe_existing_directory(Path(workspace["workspace_root"]))
        record = json.loads(_read(root, ".sceneops/game-architecture.json"))
        architecture = record.get("code_architecture")
        sources = json.loads(Path(__file__).with_name("runtime_v1_sources.json").read_text())
        if architecture not in sources or record.get("architecture_version", 1) != 1:
            raise GameProjectError("当前工程架构没有可用的运行代码迁移版本。")
        scaffold = record.get("scaffold", {})
        if scaffold.get("initialization_status") != "generated":
            raise GameProjectError("当前工程不是此版本生成的工程，请使用代码编辑任务接入运行资源。")
        generated = scaffold.get("generated_files", [])
        desired = json.loads(Path(__file__).with_name("runtime_v1_targets.json").read_text())[architecture]
        files, conflicts = [], []
        for relative, ancestor in sources[architecture].items():
            if relative not in generated:
                raise GameProjectError(f"运行代码 {relative} 不在工程生成记录中。")
            previous = _read(root, relative)
            proposed, conflict = _merge(previous, ancestor, desired[relative])
            if conflict:
                conflicts.append(relative)
            if previous != proposed:
                files.append({"path": relative, "previous": previous, "proposed": proposed})
        return {"project_id": project_id, "workspace_id": workspace_id,
                "migration_version": MIGRATION_VERSION, "architecture": architecture,
                "files": files, "conflicts": conflicts,
                "status": "conflict" if conflicts else "ready" if files else "current"}

    def apply(self, project_id: str, workspace_id: str, preview: dict) -> dict:
        # Recompute the proposal rather than trusting caller-supplied paths or code.
        current = self.preview(project_id, workspace_id)
        if current != preview:
            raise GameProjectError("运行代码已变化，请重新预览升级。")
        if current["conflicts"]:
            raise GameProjectError("运行代码升级存在合并冲突，请由代码编辑任务解决：" + ", ".join(current["conflicts"]))
        workspace = self.repository.get_project_demo_workspace(project_id, workspace_id)
        root = self.repository._safe_existing_directory(Path(workspace["workspace_root"]))
        written = []
        try:
            for change in current["files"]:
                if _read(root, change["path"]) != change["previous"]:
                    raise GameProjectError("运行代码已变化，请重新预览升级：" + change["path"])
                GameProjects._replace_text(root / change["path"], change["proposed"])
                written.append(change)
        except Exception:
            for change in reversed(written):
                try:
                    unchanged = _read(root, change["path"]) == change["proposed"]
                except (OSError, GameProjectError):
                    unchanged = False
                if unchanged:
                    GameProjects._replace_text(root / change["path"], change["previous"])
            raise
        return {**current, "status": "applied" if written else "current"}
