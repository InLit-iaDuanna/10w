import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import assert from 'node:assert/strict';
import { test, mock } from 'node:test';
import { MemoryMessage } from '../MemoryActivity';
import { ExperienceReferences } from '../ExperienceReferences';
import { experienceApi } from '../experience-client';
Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
const tick=()=>new Promise(resolve=>setTimeout(resolve,10));
async function waitFor(condition:()=>boolean) {for(let i=0;i<100;i++){if(condition())return;await act(tick);}assert.ok(condition());}
test('empty basis occupies no space and pending learning never claims saved',async()=>{
 const host=document.createElement('div');const root=createRoot(host);const cache=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false,gcTime:0}}});
 const uses=mock.method(experienceApi,'uses',async()=>[]);const activity=mock.method(experienceApi,'activity',async()=>({origin_key:'message:m1',events:[],batches:[],pending:true}));
 try{await act(async()=>root.render(<QueryClientProvider client={cache}><ExperienceReferences projectId="p1" useKey="message:m1"/><MemoryMessage projectId="p1" sourceId="message:m1" originKey="message:m1"/></QueryClientProvider>));await waitFor(()=>host.textContent!.includes('待整理'));assert.ok(!host.textContent!.includes('本次依据'));assert.ok(!host.textContent!.includes('已记住'));assert.ok(!host.textContent!.includes('已保存'));}finally{await act(async()=>root.unmount());cache.clear();uses.mock.restore();activity.mock.restore();}
});
test('remember failure preserves the draft and reports no saved state',async()=>{
 const host=document.createElement('div');const root=createRoot(host);const cache=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false,gcTime:0}}});
 const activity=mock.method(experienceApi,'activity',async()=>({origin_key:'message:m1',events:[],batches:[],pending:false}));const save=mock.method(experienceApi,'remember',async()=>{throw new Error('来源不存在');});
 try{await act(async()=>root.render(<QueryClientProvider client={cache}><MemoryMessage projectId="p1" sourceId="message:m1" originKey="message:m1" text="只能横屏"/></QueryClientProvider>));await act(async()=>host.querySelector<HTMLButtonElement>('button')!.click());await act(async()=>host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));await waitFor(()=>host.textContent!.includes('来源不存在'));assert.equal(host.querySelector('textarea')!.value,'只能横屏');assert.match(host.textContent!,/未保存/);assert.equal(save.mock.calls[0]!.arguments[0].source_id,'message:m1');const requestId=save.mock.calls[0]!.arguments[0].request_id;assert.ok(requestId);await act(async()=>host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));await waitFor(()=>save.mock.calls.length===2);assert.equal(save.mock.calls[1]!.arguments[0].request_id,requestId);}finally{await act(async()=>root.unmount());cache.clear();activity.mock.restore();save.mock.restore();}
});
test('candidate confirmation creates explicit source-backed request without claiming saved',async()=>{
 const host=document.createElement('div');const root=createRoot(host);const cache=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false,gcTime:0}}});
 const proposal={project_id:'p1',source_id:'message:m1',origin_key:'message:m1',title:'方向约束',content:'只能横屏',category:'constraint' as const,intent:'candidate' as const,source_quote:'',entry_id:null,reference_id:null,expected_revision:null,request_id:null,resolves_event_id:null};
 const activity=mock.method(experienceApi,'activity',async()=>({origin_key:'message:m1',events:[{id:'candidate1',project_id:'p1',origin_keys:['message:m1'],operation:'remember' as const,persisted:true,state:'pending' as const,reason:'等待确认',entry_id:null,before:null,after:null,reference:null,previous_reference:null,source_ids:['message:m1'],batch_id:null,created_at:'2026-09-09T00:00:00Z',proposal,resolved_by:null}],batches:[],pending:false}));
 const save=mock.method(experienceApi,'remember',async()=>{throw new Error('测试未保存');});
 try{await act(async()=>root.render(<QueryClientProvider client={cache}><MemoryMessage projectId="p1" sourceId="message:m1" originKey="message:m1"/></QueryClientProvider>));await waitFor(()=>host.textContent!.includes('查看并确认'));assert.ok(!host.textContent!.includes('已保存'));await act(async()=>Array.from(host.querySelectorAll<HTMLButtonElement>('button')).find(button=>button.textContent==='查看并确认')!.click());assert.equal(host.querySelector('textarea')!.value,'只能横屏');await act(async()=>host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));await waitFor(()=>save.mock.calls.length===1);assert.equal(save.mock.calls[0]!.arguments[0].intent,'explicit');assert.equal(save.mock.calls[0]!.arguments[0].resolves_event_id,'candidate1');assert.equal(save.mock.calls[0]!.arguments[0].source_id,'message:m1');}finally{await act(async()=>root.unmount());cache.clear();activity.mock.restore();save.mock.restore();}
});
test('failed empty context remains visible and never claims context was provided',async()=>{
 const host=document.createElement('div');const root=createRoot(host);const cache=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false,gcTime:0}}});
 const uses=mock.method(experienceApi,'uses',async()=>[{id:'u1',project_id:'p1',use_key:'task:t1:call:c1',origin_key:'task:t1',items:[],project_memories:[],notice:'',truncated:false,persisted:true,failure_reason:'项目决定读取失败',created_at:'2026-09-09T00:00:00Z'}]);
 try{await act(async()=>root.render(<QueryClientProvider client={cache}><ExperienceReferences projectId="p1" useKey="task:t1:call:c1"/></QueryClientProvider>));await waitFor(()=>host.textContent!.includes('项目决定读取失败'));assert.match(host.textContent!,/本次记忆暂不可用/);assert.ok(!host.textContent!.includes('已提供给本次请求'));}finally{await act(async()=>root.unmount());cache.clear();uses.mock.restore();}
});
test('task terminal transition refreshes previously empty learning activity',async()=>{
 const host=document.createElement('div');const root=createRoot(host);const cache=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false,gcTime:0}}});
 let terminal=false;const activity=mock.method(experienceApi,'activity',async()=>({origin_key:'task:t1',events:[],batches:[],pending:terminal}));
 const content=(active:boolean)=><QueryClientProvider client={cache}><MemoryMessage projectId="p1" sourceId="task:t1:goal" originKey="task:t1" active={active}/></QueryClientProvider>;
 try{await act(async()=>root.render(content(true)));await waitFor(()=>activity.mock.calls.length===1);terminal=true;await act(async()=>root.render(content(false)));await waitFor(()=>host.textContent!.includes('待整理'));assert.ok(activity.mock.calls.length>=2);}finally{await act(async()=>root.unmount());cache.clear();activity.mock.restore();}
});
