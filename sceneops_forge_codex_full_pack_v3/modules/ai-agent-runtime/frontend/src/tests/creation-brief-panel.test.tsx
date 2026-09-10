import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import assert from 'node:assert/strict';
import { test, mock } from 'node:test';
import { CreationBriefPanel } from '../CreationBriefPanel';
import { agentTasks, type AgentTask } from '../client';

Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});

test('brief requires a click, confirms displayed version and retains content after authorization failure',async()=>{
  const task={id:'native',project_id:'project',provider_id:'codebuddycli',provider_model:'configured',
    authorization_card:{id:'card',permission_mode:'scoped',workspace_root:'/registered/game',scope:'当前任务',cost_notice:'费用未知'}} as AgentTask;
  const brief={version:7,content:'灯塔岛：移动、点灯、返回安全区。',confirmed_at:null};
  const read=mock.method(agentTasks,'creationBrief',async()=>brief);
  const save=mock.method(agentTasks,'saveCreationBrief',async()=>brief);
  const authorize=mock.method(agentTasks,'authorize',async()=>{throw new Error('执行器暂不可用');});
  const cache=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false,gcTime:0}}});
  const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
  try {
    await act(async()=>root.render(<QueryClientProvider client={cache}><CreationBriefPanel task={task}/></QueryClientProvider>));
    await act(async()=>{await new Promise(resolve=>setTimeout(resolve,10));});
    assert.equal(host.querySelector('textarea')?.value,brief.content);
    assert.equal(authorize.mock.callCount(),0);
    const button=Array.from(host.querySelectorAll('button')).find(value=>value.textContent==='确认简报并开始制作')!;
    await act(async()=>button.click());
    await act(async()=>{await new Promise(resolve=>setTimeout(resolve,10));});
    assert.equal(save.mock.callCount(),0);
    assert.deepEqual(authorize.mock.calls[0]!.arguments,['native',{
      authorization_card_id:'card',accept_unknown_cost:true,accept_full_access:false,creation_brief_version:7}]);
    assert.equal(host.querySelector('textarea')?.value,brief.content);
    assert.ok(host.textContent?.includes('执行器暂不可用'));
  } finally {
    read.mock.restore();save.mock.restore();authorize.mock.restore();
    await act(async()=>root.unmount());host.remove();cache.clear();
  }
});
