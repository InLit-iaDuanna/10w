"""New projects start neutral; existing game content and legacy migration inputs survive."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_project_workspace.game_projects import native_template_files, template_files


@pytest.mark.parametrize('architecture', ['object-component', 'ecs'])
def test_native_scaffold_initialization_preserves_user_changes(architecture):
    with TemporaryDirectory() as temporary:
        parent = Path(temporary).resolve()
        repository = SqliteWorkspaceRepository(parent / 'state.sqlite3')
        project = repository.create_folder_project(parent, 'game')
        repository.commit_design_version(project.project_id, 1, {'title': '空白制作'})
        selection = {'code_architecture': architecture, 'architecture_label': architecture}
        scaffold = repository.initialize_game_project(project.project_id, selection, 1)
        root = Path(project.root_path)
        package = json.loads((root / 'package.json').read_text())
        assert package['scripts']['build'] == 'tsc --noEmit && vite build'
        assert ('miniplex' in package['dependencies']) == (architecture == 'ecs')
        assert 'src/game/sceneops-demo-assets.ts' not in scaffold['generated_files']
        assert 'collectibles' not in (root / 'src/main.ts').read_text()
        consumer = 'src/game/world.ts' if architecture == 'ecs' else 'src/game/objects/SceneObject.ts'
        assert 'createDemoAsset' in (root / consumer).read_text()
        assert 'sceneops_id' in (root / consumer).read_text()
        (root / 'src/main.ts').write_text('// actual user game\n')
        reopened = repository.initialize_game_project(project.project_id, selection, 1)
        assert reopened['baseline_commit'] == scaffold['baseline_commit']
        assert (root / 'src/main.ts').read_text() == '// actual user game\n'
        assert json.loads((root / '.sceneops/game-architecture.json').read_text())['template_kind'] == 'native-light'


@pytest.mark.parametrize('architecture', ['object-component', 'ecs'])
def test_legacy_migration_template_still_contains_original_game(architecture):
    legacy = template_files(architecture)
    neutral = native_template_files(architecture)
    assert 'src/game/sceneops-demo-assets.ts' in legacy
    assert 'src/game/sceneops-demo-assets.ts' not in neutral
    assert 'src/game/sceneops-test.ts' in legacy
    assert 'src/game/sceneops-test.ts' not in neutral
