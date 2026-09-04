import { buildWorldEditorScreen, type WorldEditorInput, type WorldEditorScreen } from '../editor-state.ts';

export default function WorldGraphEditor(input: WorldEditorInput): WorldEditorScreen {
  return buildWorldEditorScreen('scene.world.graph', '世界图', input, [
    { id: 'graph-scope', label: '范围', value: ['zones', 'regions', 'paths', 'relations'] },
    { id: 'gameplay-boundary', label: '玩法逻辑', value: '仅引用公开稳定 ID' },
  ]);
}
