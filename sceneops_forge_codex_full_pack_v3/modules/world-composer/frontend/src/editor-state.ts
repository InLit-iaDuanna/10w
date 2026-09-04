import type { JsonValue, WorldExecutionMode } from './contracts.ts';
import { executionLabel } from './execution.ts';

export type WorldEditorStatus =
  | 'loading'
  | 'empty'
  | 'ready'
  | 'failed'
  | 'disconnected'
  | 'permission-denied'
  | 'module-disabled'
  | 'stale'
  | 'suspended';

export interface WorldEditorInput {
  status: WorldEditorStatus;
  mode: WorldExecutionMode;
  sceneId: string | null;
  sceneVersion: string | null;
  detail?: string;
}

export interface WorldEditorScreen {
  editorId: string;
  title: string;
  status: WorldEditorStatus;
  statusLabel: string;
  mode: WorldExecutionMode;
  modeLabel: string;
  sceneLabel: string;
  detail: string;
  actions: Array<{ commandId: string; label: string }>;
  sections: Array<{ id: string; label: string; value: JsonValue }>;
}

const statusLabels: Record<WorldEditorStatus, string> = {
  loading: '正在加载',
  empty: '暂无内容',
  ready: '就绪',
  failed: '失败',
  disconnected: '集成未连接',
  'permission-denied': '权限不足',
  'module-disabled': '模块已停用',
  stale: '场景版本已过期',
  suspended: '渲染已暂停',
};

const defaultDetails: Record<WorldEditorStatus, string> = {
  loading: '正在读取场景数据。',
  empty: '选择或打开一个场景以继续。',
  ready: '场景数据可检查。',
  failed: '加载失败；请查看结构化错误后重试。',
  disconnected: '所需外部集成当前不可用。',
  'permission-denied': '当前用户缺少此编辑器所需权限。',
  'module-disabled': 'World Composer 功能开关当前已关闭。',
  stale: '编辑器绑定的场景版本与当前版本不一致。',
  suspended: '编辑器隐藏或未激活，连续渲染循环已停止。',
};

function actionsFor(status: WorldEditorStatus): WorldEditorScreen['actions'] {
  if (status === 'failed') return [{ commandId: 'scene.editor.retry', label: '重试' }];
  if (status === 'disconnected') return [{ commandId: 'integration.open', label: '检查集成' }];
  if (status === 'stale') return [{ commandId: 'scene.version.open', label: '打开精确版本' }];
  return [];
}

export function buildWorldEditorScreen(
  editorId: string,
  title: string,
  input: WorldEditorInput,
  sections: WorldEditorScreen['sections'] = [],
): WorldEditorScreen {
  return {
    editorId,
    title,
    status: input.status,
    statusLabel: statusLabels[input.status],
    mode: input.mode,
    modeLabel: executionLabel(input.mode),
    sceneLabel:
      input.sceneId && input.sceneVersion
        ? `${input.sceneId} · ${input.sceneVersion}`
        : '未选择场景',
    detail: input.detail ?? defaultDetails[input.status],
    actions: actionsFor(input.status),
    sections,
  };
}
