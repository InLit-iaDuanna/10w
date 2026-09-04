import { buildWorldEditorScreen, type WorldEditorInput, type WorldEditorScreen } from '../editor-state.ts';

export default function ObjectInspectorEditor(input: WorldEditorInput): WorldEditorScreen {
  return buildWorldEditorScreen('scene.object.inspector', '对象检查器', input, [
    { id: 'transforms', label: '变换', value: 'local / world' },
    { id: 'mutation', label: '修改', value: '仅通过 ChangeSet' },
  ]);
}
