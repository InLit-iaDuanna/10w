"""Real-file registry identity, version, provenance and scoped-path behavior."""
from contextlib import contextmanager
from types import SimpleNamespace
import sqlite3

import pytest
from sceneops_harness import HarnessError
from sceneops_ai_agents.workspace_sources import workspace_sources, confirm_source_rename


class Records:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def fixture(tmp_path):
    root = tmp_path / 'game'
    root.mkdir()
    (root / 'src').mkdir()
    card = SimpleNamespace(workspace_id='workspace_a', workspace_root=str(root))
    task = SimpleNamespace(id='task_a', project_id='project_a', authorization_card=card, actions=[])
    service = SimpleNamespace(records=Records(tmp_path / 'sources.db'),
        project_demo_workspace=lambda *args, **kwargs: None)
    return service, task, root


def test_native_sources_are_workspace_scoped_and_versioned(tmp_path):
    service, task, root = fixture(tmp_path)
    file = root / 'src/main.ts'
    file.write_text('export const speed = 1;')
    initial, truncated = workspace_sources(service, task)
    assert not truncated and len(initial) == 1
    assert initial[0].origin == 'workspace'
    file.write_text('export const speed = 2;')
    changed, _ = workspace_sources(service, task, native_round=True)
    assert changed[0].id == initial[0].id
    assert changed[0].source_version == initial[0].source_version + 1
    assert changed[0].origin == 'native-workspace'
    assert changed[0].source_task_id == task.id
    assert changed[0].latest_write_request_id is None and task.actions == []
    task.id = 'task_b'
    assert workspace_sources(service, task)[0][0].id == initial[0].id
    file.unlink()
    assert workspace_sources(service, task)[0] == []
    file.write_text('export const newFile = true;')
    assert workspace_sources(service, task)[0][0].id != initial[0].id


def test_confirmed_rename_preserves_identity_and_rejects_conflict(tmp_path):
    service, task, root = fixture(tmp_path)
    old = root / 'src/main.ts'
    old.write_text('export {};')
    entry = workspace_sources(service, task)[0][0]
    old.rename(root / 'src/game.ts')
    assert confirm_source_rename(service, task, entry.id, 'src/game.ts', entry.source_version) == entry.id
    moved = workspace_sources(service, task)[0][0]
    assert moved.id == entry.id and moved.path == 'src/game.ts'
    assert moved.source_version == entry.source_version + 1
    with pytest.raises(HarnessError):
        confirm_source_rename(service, task, entry.id, '../escape.ts', moved.source_version)
    with pytest.raises(HarnessError):
        confirm_source_rename(service, task, entry.id, 'src/other.ts', entry.source_version)


def test_source_inventory_does_not_publish_symlinks_or_managed_content(tmp_path):
    service, task, root = fixture(tmp_path)
    secret = tmp_path / 'secret.ts'
    secret.write_text('private')
    (root / 'src/link.ts').symlink_to(secret)
    (root / 'src/game').mkdir()
    (root / 'src/game/sceneops-demo-content.ts').write_text('managed')
    assert workspace_sources(service, task)[0] == []

def test_rename_can_be_confirmed_after_native_inventory_observed_both_paths(tmp_path):
    from sceneops_ai_agents.workspace_sources import source_registrations
    service, task, root = fixture(tmp_path)
    (root / 'src/old.ts').write_text('export const speed = 1;')
    original = workspace_sources(service, task)[0][0]
    (root / 'src/old.ts').rename(root / 'src/new.ts')
    inventory = source_registrations(service, task)
    deleted = next(entry for entry in inventory if entry.id == original.id)
    target = next(entry for entry in inventory if entry.path == 'src/new.ts')
    assert deleted.deleted
    with pytest.raises(HarnessError):
        confirm_source_rename(service, task, original.id, target.path, deleted.source_version)
    confirm_source_rename(service, task, original.id, target.path, deleted.source_version, target.source_version)
    actual = workspace_sources(service, task)[0]
    assert len(actual) == 1 and actual[0].id == original.id
