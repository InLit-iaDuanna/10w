"""Source migration retains user edits and never applies conflicting/stale previews."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sceneops_project_workspace.game_projects import GameProjectError, template_files
from sceneops_project_workspace.runtime_upgrade import DemoRuntimeUpgrade
import sceneops_project_workspace.runtime_upgrade as migration


def project(tmp_path, architecture="object-component"):
    ancestors = json.loads(Path(migration.__file__).with_name("runtime_v1_sources.json").read_text())[architecture]
    for relative, content in {**template_files(architecture), **ancestors}.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (tmp_path / ".sceneops").mkdir()
    (tmp_path / ".sceneops/game-architecture.json").write_text(json.dumps({
        "code_architecture": architecture, "architecture_version": 1,
        "scaffold": {"initialization_status": "generated", "generated_files": list(ancestors)}}))
    repo = SimpleNamespace(get_project_demo_workspace=lambda *_: {"workspace_root": str(tmp_path)},
                           _safe_existing_directory=lambda path: path)
    return DemoRuntimeUpgrade(repo)


@pytest.mark.parametrize("architecture", ["object-component", "ecs"])
def test_migration_preserves_independent_user_code_and_is_idempotent(tmp_path, architecture):
    service = project(tmp_path, architecture)
    path = tmp_path / "src/main.ts"
    path.write_text("// User's independent customization\n" + path.read_text())
    preview = service.preview("p", "w")
    assert preview["status"] == "ready"
    assert not preview["conflicts"]
    service.apply("p", "w", preview)
    assert path.read_text().startswith("// User's independent customization\n")
    assert service.preview("p", "w")["status"] == "current"


def test_conflict_and_stale_preview_do_not_mutate(tmp_path):
    service = project(tmp_path)
    preview = service.preview("p", "w")
    path = tmp_path / "src/game/objects/KeyDoor.ts"
    path.write_text("// User completely replaced this behavior\n")
    before = path.read_text()
    with pytest.raises(GameProjectError, match="重新预览"):
        service.apply("p", "w", preview)
    conflict = service.preview("p", "w")
    assert "src/game/objects/KeyDoor.ts" in conflict["conflicts"]
    with pytest.raises(GameProjectError, match="合并冲突"):
        service.apply("p", "w", conflict)
    assert path.read_text() == before


def test_preview_rejects_symlink_and_apply_rejects_tampering(tmp_path):
    service = project(tmp_path)
    preview = service.preview("p", "w")
    preview["files"][0]["proposed"] = "untrusted source"
    with pytest.raises(GameProjectError, match="重新预览"):
        service.apply("p", "w", preview)
    path = tmp_path / "src/main.ts"
    path.unlink()
    path.symlink_to(tmp_path / "src/game/Game.ts")
    with pytest.raises(GameProjectError, match="符号链接"):
        service.preview("p", "w")


def test_target_does_not_follow_future_template_generator(tmp_path, monkeypatch):
    import sceneops_project_workspace.game_projects as templates
    service = project(tmp_path)
    before = service.preview("p", "w")
    monkeypatch.setattr(templates, "template_files", lambda _: {"src/main.ts": "future unrelated behavior"})
    assert service.preview("p", "w") == before


def test_concurrent_edits_survive_apply_and_rollback(tmp_path, monkeypatch):
    service = project(tmp_path)
    preview = service.preview("p", "w")
    first, second = preview["files"][:2]
    original_write = migration.GameProjects._replace_text

    def edit_during_apply(path, content):
        original_write(path, content)
        if path == tmp_path / first["path"]:
            path.write_text("// Concurrent edit of migrated file\n")
            (tmp_path / second["path"]).write_text("// Concurrent edit of pending file\n")

    monkeypatch.setattr(migration.GameProjects, "_replace_text", staticmethod(edit_during_apply))
    with pytest.raises(GameProjectError, match="重新预览"):
        service.apply("p", "w", preview)
    assert (tmp_path / first["path"]).read_text() == "// Concurrent edit of migrated file\n"
    assert (tmp_path / second["path"]).read_text() == "// Concurrent edit of pending file\n"
