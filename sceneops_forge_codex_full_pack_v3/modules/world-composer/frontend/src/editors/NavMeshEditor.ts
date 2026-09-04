import { buildWorldEditorScreen, type WorldEditorInput, type WorldEditorScreen } from '../editor-state.ts';

export default function NavMeshEditor(input: WorldEditorInput): WorldEditorScreen {
  return buildWorldEditorScreen('scene.navmesh', '导航网格', input, [
    { id: 'validation', label: '校验', value: ['reachability', 'path continuity'] },
    { id: 'missing-data', label: '缺少输入', value: 'blocked' },
  ]);
}
