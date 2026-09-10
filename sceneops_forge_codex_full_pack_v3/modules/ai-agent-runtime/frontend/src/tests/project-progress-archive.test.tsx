import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { expect, test, vi } from 'vitest';
import { ProjectProgressTool } from '../ProjectGameTools';
import { agentTasks } from '../client';
vi.mock('../AgentTaskWorkbench', () => ({ AgentTaskActivity: () => null, TaskCard: () => null, GameRuntimePanel: () => null }));
vi.mock('../client', () => ({ agentTaskKeys: { list: (id: string) => ['agent-tasks', 'list', id] }, agentTasks: { progress: vi.fn(), archive: vi.fn() } }));
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

test('archive hides a record, archived view restores it, and failed requests leave it visible', async () => {
  let archived = false;
  const task = () => ({ id:'task-fixture', project_id:'p', goal:'测试任务', status:'failed', owner_pid:null, archived,
    authorization_card:{card_id:'card'}, created_at:'2026-09-08T00:00:00Z' });
  vi.mocked(agentTasks.progress).mockImplementation(async (_id, view) => ({tasks: archived === view ? [task()] : []}) as never);
  vi.mocked(agentTasks.archive).mockImplementation(async (_id, body) => { archived = body.archived; return task() as never; });
  const host = document.createElement('div'); document.body.append(host);
  const root=createRoot(host), cache=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});
  const button=(label:string)=>[...host.querySelectorAll('button')].find(item=>item.textContent===label)!;
  const settle=async()=>{ await act(async()=>{await new Promise(resolve=>setTimeout(resolve,40));}); };
  try {
    await act(async()=>root.render(<QueryClientProvider client={cache}><ProjectProgressTool projectId="p"/></QueryClientProvider>)); await settle();
    await act(async()=>button('归档').click()); await settle();
    expect(host.textContent).not.toContain('测试任务');
    await act(async()=>button('查看已归档').click()); await settle();
    expect(host.textContent).toContain('测试任务');
    await act(async()=>button('恢复').click()); await settle();
    await act(async()=>button('返回任务记录').click()); await settle();
    expect(host.textContent).toContain('测试任务');
    vi.mocked(agentTasks.archive).mockRejectedValueOnce(new Error('保存失败'));
    await act(async()=>button('归档').click()); await settle();
    expect(host.textContent).toContain('测试任务');
    expect(host.querySelector('[role="alert"]')?.textContent).toBe('保存失败');
  } finally { await act(async()=>root.unmount());cache.clear();host.remove();vi.resetAllMocks(); }
});
