import { buildWorldEditorScreen, type WorldEditorInput, type WorldEditorScreen } from '../editor-state.ts';

export default function PathRegionEditor(input: WorldEditorInput): WorldEditorScreen {
  return buildWorldEditorScreen('scene.path-region', '路径与区域', input, [
    { id: 'units', label: '距离单位', value: 'meters' },
    { id: 'approval', label: '生产修改', value: '等待 ChangeSet 审批' },
  ]);
}
