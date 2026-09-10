import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import assert from 'node:assert/strict';
import { test, mock } from 'node:test';
import { ExperiencePanel } from '../ExperiencePanel';
import { ExperienceReferences } from '../ExperienceReferences';
import { experienceApi, type ExperienceEntry, type ExperienceStatus, type ExperienceTopic } from '../experience-client';
Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
const entry:ExperienceEntry={id:'e1',project_id:'p1',scope:'shared',memory_category:null,kind:'procedure',title:'验证构建',content:'**关键做法**：运行检查后记录结果',applicability:'修改源码后',topics:['build_delivery','engineering_workflow'],domains:['code'],platforms:['web'],status:'supported',enabled:true,revision:1,evidence:[],created_at:'2026-09-08T00:00:00Z',updated_at:'2026-09-08T00:00:00Z'};
const other:ExperienceEntry={...entry,id:'e2',title:'另一条经验',topics:['motion_interaction'],platforms:['blender'],domains:[]};
const topics:ExperienceTopic[]=[{id:'build_delivery',label:'构建与交付',description:'编译、打包与发布'},{id:'motion_interaction',label:'体感与交互',description:'输入与交互'},{id:'engineering_workflow',label:'工程与协作',description:'工程工作方法'},{id:'scene_animation',label:'场景与动画',description:'动画与场景'}];
const status:ExperienceStatus={settings:{use_enabled:true,learn_enabled:true,batch_call_limit:2,daily_call_limit:20,enabled_at:'2026-09-08T00:00:00Z',timezone:'Asia/Shanghai'},day:'2026-09-08',calls_used:1,cost_usd:null,pending_sources:1,batches:[],last_error:null};
const tick=()=>new Promise(resolve=>setTimeout(resolve,10));
async function waitFor(condition:()=>boolean) {
 for(let attempt=0;attempt<100;attempt++){if(condition())return;await act(tick);}
 assert.ok(condition(),'expected DOM state did not arrive within 1 second');
}
async function mountLibrary() {
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 const cache=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false,gcTime:0}}});
 const originalShow=window.HTMLDialogElement.prototype.showModal;const originalClose=window.HTMLDialogElement.prototype.close;
 window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};window.HTMLDialogElement.prototype.close=function(){this.open=false;};
 const mocks=[mock.method(experienceApi,'projectMemory',async()=>({project_id:'p1',references:[],entries:[]})),mock.method(experienceApi,'status',async()=>status),mock.method(experienceApi,'topics',async()=>topics),mock.method(experienceApi,'entries',async()=>[entry,other,{...entry,id:'local-case',scope:'project',kind:'case',title:'项目故障记录'}]),mock.method(experienceApi,'entry',async(_project:string|null,id:string)=>id==='e2'?other:entry),mock.method(experienceApi,'revisions',async()=>[])];
 await act(async()=>root.render(<QueryClientProvider client={cache}><ExperiencePanel projectId="p1"/></QueryClientProvider>));
 await act(async()=>host.querySelector<HTMLButtonElement>('button')!.click());
 const dialog=document.querySelector<HTMLDialogElement>('.experience-dialog')!;
 await act(async()=>dialog.querySelector<HTMLButtonElement>('#experience-tab-library')!.click());
 await waitFor(()=>dialog.querySelectorAll('.experience-entry').length===2 && !!dialog.querySelector('[aria-label="经验主题"] button[title="编译、打包与发布"]'));
 return {host,dialog,cache,cleanup:async()=>{await act(async()=>root.unmount());cache.clear();host.remove();for(const value of mocks)value.mock.restore();window.HTMLDialogElement.prototype.showModal=originalShow;window.HTMLDialogElement.prototype.close=originalClose;}};
}
const button=(host:Element,text:string)=>Array.from(host.querySelectorAll<HTMLButtonElement>('button')).find(value=>value.textContent?.trim()===text)!;
async function editSelected(dialog:Element) {await waitFor(()=>!!dialog.querySelector('[aria-label="编辑经验"]'));await act(async()=>dialog.querySelector<HTMLButtonElement>('[aria-label="编辑经验"]')!.click());}

test('library separates browsing from settings and supports authoritative topics and tool filters',async()=>{
 const ui=await mountLibrary();const {dialog}=ui;
 try{
  const library=dialog.querySelector<HTMLElement>('#experience-view-library')!;const settings=dialog.querySelector<HTMLElement>('#experience-view-settings')!;
  assert.equal(settings.hidden,true);assert.equal(library.querySelector('input[type=number]'),null);
  const build=dialog.querySelector<HTMLButtonElement>('[aria-label="经验主题"] button[title="编译、打包与发布"]')!;
  assert.equal(build.querySelector('small')!.textContent,'1');
  await act(async()=>build.click());assert.equal(dialog.querySelectorAll('.experience-entry').length,1);assert.match(dialog.querySelector('.experience-entry')!.textContent!,/验证构建/);
  await act(async()=>dialog.querySelector<HTMLButtonElement>('[aria-label="经验主题"] button')!.click());
  const tools=dialog.querySelector<HTMLSelectElement>('[aria-label="工具 / 平台"]')!;
  assert.ok(Array.from(tools.options).some(option=>option.value==='blender'));
  await act(async()=>{tools.value='blender';tools.dispatchEvent(new Event('change',{bubbles:true}));});
  assert.equal(dialog.querySelectorAll('.experience-entry').length,1);assert.match(dialog.querySelector('.experience-entry')!.textContent!,/另一条经验/);
  await act(async()=>{tools.value='all';tools.dispatchEvent(new Event('change',{bubbles:true}));});
  await act(async()=>dialog.querySelector<HTMLButtonElement>('.experience-entry')!.click());await waitFor(()=>!!dialog.querySelector('.experience-reading'));
  assert.equal(dialog.querySelector('.experience-editor'),null);assert.match(dialog.querySelector('.experience-applicability')!.textContent!,/修改源码后/);assert.equal(dialog.querySelector('.experience-reading .sceneops-markdown strong')!.textContent,'关键做法');
  await editSelected(dialog);const boxes=Array.from(dialog.querySelectorAll<HTMLInputElement>('.experience-topic-picker input'));
  assert.equal(boxes.filter(box=>box.checked).length,2);
  await act(async()=>boxes.find(box=>!box.checked)!.click());assert.equal(boxes.filter(box=>box.checked).length,3);assert.ok(boxes.filter(box=>!box.checked).every(box=>box.disabled));
  await act(async()=>dialog.querySelector<HTMLButtonElement>('#experience-tab-settings')!.click());assert.equal(settings.hidden,false);assert.equal(library.hidden,true);assert.ok(settings.querySelector('[aria-label="每日调用上限"]'));
  await act(async()=>dialog.querySelector<HTMLButtonElement>('#experience-tab-activity')!.click());assert.equal(dialog.querySelector<HTMLElement>('#experience-view-activity')!.hidden,false);assert.match(dialog.querySelector('#experience-view-activity')!.textContent!,/今日费用未知/);
 }finally{await ui.cleanup();}
});
test('per-entry drafts survive selection, remote revisions, failed save and close while preserving base revision',async()=>{
 const ui=await mountLibrary();const {dialog,cache,host}=ui;let expectedRevision:number|undefined;
 const patch=mock.method(experienceApi,'patch',async(_project:string|null,_id:string,body:Parameters<typeof experienceApi.patch>[2])=>{expectedRevision=body.expected_revision;throw new Error('版本冲突');});
 try{
  await act(async()=>dialog.querySelector<HTMLButtonElement>('.experience-entry')!.click());await editSelected(dialog);
  const field=dialog.querySelector<HTMLTextAreaElement>('[aria-label="经验内容"]')!;
  await act(async()=>{Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value')!.set!.call(field,'保留我的修订');field.dispatchEvent(new Event('input',{bubbles:true}));});
  await act(async()=>dialog.querySelectorAll<HTMLButtonElement>('.experience-entry')[1]!.click());await waitFor(()=>dialog.querySelector('.experience-detail-heading h3')?.textContent==='另一条经验');
  await act(async()=>dialog.querySelectorAll<HTMLButtonElement>('.experience-entry')[0]!.click());await waitFor(()=>dialog.querySelector('.experience-detail-heading h3')?.textContent==='验证构建');await editSelected(dialog);
  assert.equal(dialog.querySelector<HTMLTextAreaElement>('[aria-label="经验内容"]')!.value,'保留我的修订');
  await act(async()=>{cache.setQueryData(['experience','entry','p1','e1'],{...entry,revision:2,content:'后台更新'});await tick();});
  assert.equal(dialog.querySelector<HTMLTextAreaElement>('[aria-label="经验内容"]')!.value,'保留我的修订');assert.match(dialog.textContent!,/服务器已更新到 v2/);
  await act(async()=>dialog.querySelector('.experience-editor')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));await waitFor(()=>dialog.textContent!.includes('版本冲突'));
  assert.equal(expectedRevision,1);assert.equal(dialog.querySelector<HTMLTextAreaElement>('[aria-label="经验内容"]')!.value,'保留我的修订');
  await act(async()=>dialog.querySelector<HTMLButtonElement>('[aria-label="关闭经验"]')!.click());assert.equal(dialog.open,false);
  await act(async()=>host.querySelector<HTMLButtonElement>('button')!.click());assert.equal(dialog.querySelector<HTMLTextAreaElement>('[aria-label="经验内容"]')!.value,'保留我的修订');
  await act(async()=>button(dialog,'放弃本次编辑并重新读取').click());await waitFor(()=>dialog.querySelector<HTMLTextAreaElement>('[aria-label="经验内容"]')?.value===entry.content);
  assert.equal(dialog.querySelector('.experience-entry')!.textContent!.includes('有草稿'),false);
 }finally{patch.mock.restore();await ui.cleanup();}
});
test('provided references distinguish context from adoption and expose fetch errors',async()=>{
 const host=document.createElement('div');const root=createRoot(host);const cache=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false,gcTime:0}}});
 const uses=mock.method(experienceApi,'uses',async()=>{throw new Error('服务未连接');});
 try{await act(async()=>{root.render(<QueryClientProvider client={cache}><ExperienceReferences projectId="p1" useKey="task:t1:"/></QueryClientProvider>);await tick();});
  await waitFor(()=>host.textContent!.includes('服务未连接'));
  assert.match(host.textContent!,/本次依据读取失败/);assert.match(host.textContent!,/服务未连接/);
 }finally{await act(async()=>root.unmount());cache.clear();uses.mock.restore();}
});

test('general experience keeps existing project cases accessible through scope filter',async()=>{
 const ui=await mountLibrary();try{const scope=ui.dialog.querySelector<HTMLSelectElement>('[aria-label="经验范围"]')!;assert.equal(scope.hidden,false);assert.equal(scope.value,'shared');await act(async()=>{scope.value='project';scope.dispatchEvent(new Event('change',{bubbles:true}));});assert.match(ui.dialog.querySelector('.experience-entry-list')!.textContent!,/项目故障记录/);}finally{await ui.cleanup();}
});
