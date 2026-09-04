import { buildWorldEditorScreen, type WorldEditorInput, type WorldEditorScreen } from '../editor-state.ts';

export default function AnnotationListEditor(input: WorldEditorInput): WorldEditorScreen {
  return buildWorldEditorScreen('scene.annotations', '空间标注', input, [
    { id: 'annotation-types', label: '类型', value: 9 },
    { id: 'voice-policy', label: '语音', value: '仅创建草稿' },
  ]);
}
