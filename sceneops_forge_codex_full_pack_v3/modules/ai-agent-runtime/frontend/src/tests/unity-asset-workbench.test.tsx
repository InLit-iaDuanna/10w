import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import assert from 'node:assert/strict';
import { test, mock } from 'node:test';
import { UnityAssetWorkbench } from '../UnityAssetWorkbench';
import { agentTasks, type AgentTask, type UnityContentSnapshot } from '../client';

Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
const snapshot:UnityContentSnapshot={task_id:'unity-task',project_id:'p1',workspace_id:'u1',source_asset_id:'asset-1',available_source_version:2,imported_source_version:2,editor_version:'2022.3.62f3c1',project_root:'/isolated/unity',scene_path:'Assets/Main.unity',mode:'cached',status:'ready',dirty:false,playing:false,compiling:false,instances:[{instance_id:'instance-1',position:[1,2,3],interaction_distance:2,requires_key:true}],readback:{},notice:'缓存回读'};
const task={id:'unity-task',status:'review_required',actions:[],grant:{revoked:false,expires_at:'2099-01-01T00:00:00Z',budget:{max_steps:30}}} as unknown as AgentTask;
async function mount() {
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 const cache=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false,gcTime:0}}});
 await act(async()=>root.render(<QueryClientProvider client={cache}><UnityAssetWorkbench sourceTaskId="source-task" assetId="asset-1" assetTitle="钥匙门" sourceVersion={2} unavailable={false}/></QueryClientProvider>));
 return {host,close:async()=>{await act(async()=>root.unmount());cache.clear();host.remove();}};
}
const flush=()=>act(async()=>{await new Promise(resolve=>setTimeout(resolve,10));});
test('Unity entry uses selected asset identity and existing task authorization, edit includes previous fields',async()=>{
 const prepare=mock.method(agentTasks,'prepareUnityAssetTask',async()=>task);
 const readTask=mock.method(agentTasks,'get',async()=>task);
 const read=mock.method(agentTasks,'readUnityContent',async()=>snapshot);
 const action=mock.method(agentTasks,'manualUnityAction',async()=>task);
 const view=await mount();
 try {
  await act(async()=>view.host.querySelector('button')!.click());await flush();
  assert.deepEqual(prepare.mock.calls[0]?.arguments,['source-task',{asset_id:'asset-1',source_version:2}]);
  assert.match(view.host.textContent??'',/从保存记录读回/);
  assert.match(view.host.textContent??'',/Unity 许可证请以 Unity Hub 显示为准/);
  assert.match(view.host.textContent??'',/instance-1/);
  await act(async()=>view.host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));await flush();
  const body=action.mock.calls[0]?.arguments[1];
  assert.equal(body?.instance_id,'instance-1');assert.equal(body?.operation,'edit');
  assert.deepEqual(body?.expected,{position:[1,2,3],interaction_distance:2,requires_key:true});
 } finally {await view.close();prepare.mock.restore();readTask.mock.restore();read.mock.restore();action.mock.restore();}
});
test('Unity target preparation failure is visible and does not grant or execute',async()=>{
 const prepare=mock.method(agentTasks,'prepareUnityAssetTask',async()=>{throw new Error('Unity 目标未登记');});
 const authorize=mock.method(agentTasks,'authorize',async()=>task);
 const action=mock.method(agentTasks,'manualUnityAction',async()=>task);
 const view=await mount();
 try {
  await act(async()=>view.host.querySelector('button')!.click());await flush();
  assert.match(view.host.textContent??'',/Unity 目标未登记/);
  assert.equal(authorize.mock.calls.length,0);assert.equal(action.mock.calls.length,0);
 } finally {await view.close();prepare.mock.restore();authorize.mock.restore();action.mock.restore();}
});

test('renewed Unity grant counts only its own actions',async()=>{
 const renewed={...task,model_calls_used:17,actions:Array.from({length:65},()=>({state:'succeeded',effect_state:'NONE'})),grant:{...task.grant,id:'renewed',budget:{max_steps:2,max_metered_calls:2}},observations:{demo_authorization_window:{grant_id:'renewed',actions_start:64,model_calls_start:16}}} as unknown as AgentTask;
 const prepare=mock.method(agentTasks,'prepareUnityAssetTask',async()=>renewed);
 const readTask=mock.method(agentTasks,'get',async()=>renewed);
 const read=mock.method(agentTasks,'readUnityContent',async()=>snapshot);
 const view=await mount();
 try {
  await act(async()=>view.host.querySelector('button')!.click());await flush();
  assert.match(view.host.textContent??'',/已执行 1 \/ 2 个动作/);
  const inspect=Array.from(view.host.querySelectorAll('button')).find(button=>button.textContent==='刷新 Unity 状态');
  assert.equal(inspect?.disabled,false);
 } finally {await view.close();prepare.mock.restore();readTask.mock.restore();read.mock.restore();}
});

test('Play mode exposes bounded movement and interaction requests',async()=>{
 const prepare=mock.method(agentTasks,'prepareUnityAssetTask',async()=>task);
 const readTask=mock.method(agentTasks,'get',async()=>task);
 const read=mock.method(agentTasks,'readUnityContent',async()=>({...snapshot,playing:true}));
 const action=mock.method(agentTasks,'manualUnityAction',async()=>task);
 const view=await mount();
 try {
  await act(async()=>view.host.querySelector('button')!.click());await flush();
  const forward=Array.from(view.host.querySelectorAll('button')).find(button=>button.textContent==='向前移动');
  assert.equal(forward?.disabled,false);
  await act(async()=>forward!.click());await flush();
  const body=action.mock.calls[0]?.arguments[1];
  assert.equal(body?.operation,'act');assert.equal(body?.move_z,1);assert.equal(body?.duration_frames,120);
  assert.ok(body?.request_id);
 } finally {await view.close();prepare.mock.restore();readTask.mock.restore();read.mock.restore();action.mock.restore();}
});
