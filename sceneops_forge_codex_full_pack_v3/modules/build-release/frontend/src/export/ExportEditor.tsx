import type { EditorHostProps } from '@sceneops/core-ui';
import { ExportWorkbench } from './ExportWorkbench';

export default function ExportEditor({ context }: EditorHostProps) {
  return context.projectId ? <ExportWorkbench projectId={context.projectId} /> : <p>请先打开一个项目，再开始导出。</p>;
}
