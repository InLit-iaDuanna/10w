"""File assets must never silently disappear through the old recipe-only consumer."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
import pytest
from sceneops_project_workspace.game_projects import GameProjects, GameProjectError, template_files


def test_file_asset_refuses_legacy_consumer_without_overwriting_user_source():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        game = root / 'src/game'; (game / 'objects').mkdir(parents=True)
        consumer = game / 'objects/KeyDoor.ts'; consumer.write_text('// user recipe-only behavior')
        derived = game / 'sceneops-demo-content.ts'; derived.write_text('// previous playable content')
        repository = SimpleNamespace(get_project_demo_workspace=lambda *_: {'workspace_root': str(root)},
                                     _safe_existing_directory=lambda path: path)
        with pytest.raises(GameProjectError, match='LEGACY_RUNTIME_REQUIRES_EDIT'):
            GameProjects(repository).materialize_demo_content('p', 'w', {
                'project_id': 'p', 'workspace_id': 'w', 'assets': [{'source_kind': 'blender'}]})
        assert consumer.read_text() == '// user recipe-only behavior'
        assert derived.read_text() == '// previous playable content'


def test_both_architectures_await_real_asset_creation():
    objects = template_files('object-component')
    ecs = template_files('ecs')
    assert 'await createDemoAsset(asset)' in objects['src/game/objects/KeyDoor.ts']
    assert 'await createDemoAsset(asset)' in ecs['src/game/world.ts']
    assert 'await createGameWorld(scene)' in ecs['src/main.ts']
    assert 'setDemoDoorOpen' in objects['src/game/objects/KeyDoor.ts']
    assert 'setDemoDoorOpen' in ecs['src/game/systems/doorSystem.ts']
