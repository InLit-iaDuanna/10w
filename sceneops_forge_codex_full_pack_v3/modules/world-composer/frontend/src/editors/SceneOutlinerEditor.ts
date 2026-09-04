import { buildWorldEditorScreen, type WorldEditorInput, type WorldEditorScreen } from '../editor-state.ts';

export default function SceneOutlinerEditor(input: WorldEditorInput): WorldEditorScreen {
  return buildWorldEditorScreen('scene.outliner', '场景大纲', input, [
    { id: 'identity', label: '对象身份', value: 'sceneops_id' },
    { id: 'selection', label: '选择同步', value: '按稳定 ID' },
  ]);
}
