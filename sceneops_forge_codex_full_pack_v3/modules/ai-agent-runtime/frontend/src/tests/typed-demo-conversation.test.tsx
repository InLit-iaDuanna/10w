import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test } from 'vitest';
import { TypedDemoConversation } from '../AgentTaskWorkbench';
import type { AgentTask } from '../client';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

function task(state: AgentTask['actions'][number]['state']): AgentTask {
  return {
    status: state === 'failed' ? 'failed' : 'running',
    observations: {}, reason: state === 'failed' ? '检查未通过，源文件已保留' : null,
    actions: [{request_id:'request-1',state,action:{action_id:'action-1',capability_id:'code.file.read',
      rationale:'读取当前游戏入口',inputs:{path:'src/main.ts',command:'cat src/main.ts'}},
      reason:state === 'failed' ? '文件读取失败' : null}],
  } as AgentTask;
}

test('typed demo exposes actual action, file and command without a collapsed timeline', async () => {
  const host = document.createElement('div');
  const root = createRoot(host);
  try {
    await act(async () => root.render(<TypedDemoConversation task={task('running')} />));
    expect(host.querySelector('.agent-native-tool')?.textContent).toContain('读取源码');
    expect(host.querySelector('.agent-native-tool')?.textContent).toContain('src/main.ts');
    expect(host.querySelector('.agent-native-tool')?.textContent).toContain('执行中');
    expect(host.querySelector('.agent-typed-command')?.textContent).toBe('cat src/main.ts');
    expect(host.querySelector('.agent-typed-action')?.closest('details')).toBeNull();
    expect(host.textContent).not.toContain('项目作品');
    await act(async () => root.render(<TypedDemoConversation task={task('succeeded')} />));
    expect(host.querySelector('.agent-native-tool')?.textContent).toContain('已完成');
  } finally { await act(async () => root.unmount()); }
});

test('typed demo keeps failures visible and does not mark planned actions as complete', async () => {
  const host = document.createElement('div');
  const root = createRoot(host);
  try {
    await act(async () => root.render(<TypedDemoConversation task={task('failed')} />));
    expect(Array.from(host.querySelectorAll('[role="alert"]')).map(node => node.textContent)).toEqual(['文件读取失败','检查未通过，源文件已保留']);
    await act(async () => root.render(<TypedDemoConversation task={task('planned')} />));
    expect(host.querySelector('.agent-native-tool')?.textContent).toContain('尚未执行');
    expect(host.textContent).not.toContain('已完成');
  } finally { await act(async () => root.unmount()); }
});
