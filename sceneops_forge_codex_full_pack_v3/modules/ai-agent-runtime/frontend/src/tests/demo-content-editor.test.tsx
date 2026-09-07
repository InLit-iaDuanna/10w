import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import assert from 'node:assert/strict';
import { test, mock } from 'node:test';
import { DemoContentEditor, demoEntries } from '../DemoContentEditor';
import { agentTasks, type AgentTask } from '../client';
import type { components } from '../generated/agent-api';

Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
const content:components['schemas']['DemoContentIndex']={project_id:'p1',workspace_id:'w1',scene_version:3,assets:[],instances:[],sources:[{id:'write-1',latest_write_request_id:'write-1',path:'src/puzzle.ts',content:'export const answer=1;',source_version:2,edit_mode:'source-agent'}],unbuilt_changes:true,source_notice:'源与试玩独立'};
const task={id:'task-1',observations:{},authorization_card:{allow_blender_edit:false}} as AgentTask;

test('source target uses recorded identity and source text rather than client path',()=>{
 const entry=demoEntries(content,'candidate-old')[0]!;
 assert.deepEqual(entry.target,{project_id:'p1',workspace_id:'w1',kind:'source',id:'write-1',source_version:2,viewed_candidate_id:'candidate-old',expected_source_content:content.sources[0]!.content});
 assert.deepEqual(entry.values,{});
});

test('failed source followup retains input and request ID; project switch clears selection',async()=>{
 localStorage.clear();
 localStorage.setItem('sceneops:demo-draft:p1:w1:source:write-1',JSON.stringify({version:2,values:{},goal:'让机关按顺序触发',requestId:null,expectedSource:content.sources[0]!.content}));
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 const cache=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false,gcTime:0}}});
 const followup=mock.method(agentTasks,'continueProjectDemo',async()=>{throw new Error('范围已过期');});
 const render=(value:typeof content)=>root.render(<QueryClientProvider client={cache}><DemoContentEditor key={value.project_id} task={task} content={value} viewedCandidateId="old" unavailable={false} agentUnavailable={false} /></QueryClientProvider>);
 try {
  await act(async()=>render(content));
  const select=host.querySelector('select')!;
  await act(async()=>{select.value='source:write-1';select.dispatchEvent(new Event('change',{bubbles:true}));});
  assert.equal(host.querySelector('pre')?.textContent,content.sources[0]!.content);
  assert.equal(host.querySelector('input'),null);
  assert.equal(host.querySelector('textarea')?.value,'让机关按顺序触发');
  const form=host.querySelector('form')!;
  await act(async()=>form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
  await act(async()=>{await new Promise(resolve=>setTimeout(resolve,10));});
  assert.ok((host.textContent ?? "").includes('范围已过期'));
  const first=followup.mock.calls[0]!.arguments[1]!;
  await act(async()=>form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
  assert.equal(followup.mock.calls[1]!.arguments[1]!.request_id,first.request_id);
  assert.equal(first.target?.id,'write-1');
  assert.equal(first.goal,'让机关按顺序触发');
  assert.equal(host.querySelector('textarea')?.value,'让机关按顺序触发');
  await act(async()=>render({...content,project_id:'p2',workspace_id:'w2'}));
  assert.equal(host.querySelector('select')?.value,'');
  assert.equal(host.querySelector('textarea'),null);
 } finally {followup.mock.restore();await act(async()=>root.unmount());host.remove();cache.clear();localStorage.clear();}
});

test('external source changes preserve draft and require explicit refresh before Agent send',async()=>{
 localStorage.clear();localStorage.setItem('sceneops:demo-draft:p1:w1:source:write-1',JSON.stringify({version:2,values:{},goal:'保留我的要求',requestId:null,expectedSource:'old source'}));
 const host=document.createElement('div');const root=createRoot(host);const cache=new QueryClient({defaultOptions:{queries:{gcTime:0},mutations:{gcTime:0}}});
 try {
  await act(async()=>root.render(<QueryClientProvider client={cache}><DemoContentEditor task={task} content={content} viewedCandidateId="old" unavailable={false} agentUnavailable={false}/></QueryClientProvider>));
  await act(async()=>{const select=host.querySelector('select')!;select.value='source:write-1';select.dispatchEvent(new Event('change',{bubbles:true}));});
  assert.ok((host.textContent ?? "").includes('源已变更'));
  assert.equal(host.querySelector('textarea')?.value,'保留我的要求');
  assert.equal(Array.from(host.querySelectorAll('button')).find(button=>button.textContent==='发送修改要求')?.disabled,true);
 } finally {await act(async()=>root.unmount());cache.clear();localStorage.clear();}
});

test('shared recipe exposes current material and dimensions with real reference impact',()=>{
 const asset={id:'door-asset',title:'共享门',current_version:2,versions:[{source_version:2,recipe:{kind:'door-v1',seed:0,width_m:1.5,height_m:2.3,thickness_m:.2,material:{color_hex:'#123456',roughness:.4,metalness:.6}}}]} as components['schemas']['ProjectAssetEntry'];
 const instance={id:'door-a',title:'入口',asset_id:'door-asset',transform:{position_m:[0,0,0],rotation_y_deg:0,scale:1}} as components['schemas']['EnvironmentObject'];
 const entry=demoEntries({...content,assets:[asset],instances:[instance]},null)[0]!;
 assert.deepEqual(entry.values,{width_m:'1.5',height_m:'2.3',thickness_m:'0.2',color_hex:'#123456',roughness:'0.4',metalness:'0.6'});
 assert.equal(entry.target.source_version,2);
 assert.equal(entry.target.expected_scene_version,content.scene_version);
 assert.deepEqual(entry.impact,['入口 (door-a)']);
});
