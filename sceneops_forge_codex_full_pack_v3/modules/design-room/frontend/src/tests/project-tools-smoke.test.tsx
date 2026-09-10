import React,{act} from 'react';import {createRoot} from 'react-dom/client';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import {test,expect,vi} from 'vitest';
import {ProjectPlanningTools} from '../ProjectPlanningTools';import {journeyClient,journeyKey,type PlanningJourney} from '../journey-client';
Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
test('source tool pins its selected card when another view changes the active conversation',async()=>{
 const state={project_id:'p',root_path:'/tmp/game',revision:1,active_card_id:'a',cards:[{id:'a',title:'移动'},{id:'b',title:'场景'}],card_branches:[{card_id:'a'},{card_id:'b'}],technical_plan:{architecture_label:'ECS'}} as PlanningJourney;
 vi.spyOn(journeyClient,'get').mockResolvedValue(state);const command=vi.spyOn(journeyClient,'command');
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);const cache=new QueryClient();
 try{await act(async()=>root.render(<QueryClientProvider client={cache}><ProjectPlanningTools projectId="p" onOpenConversation={()=>{}} renderSource={(id,onDirty)=><button onClick={()=>onDirty(true)}>编辑 {id}</button>}/></QueryClientProvider>));
 await act(async()=>{await new Promise(resolve=>setTimeout(resolve,30));});
 expect(host.querySelector('select')?.value).toBe('a');
 await act(async()=>host.querySelector('button')!.click());
 expect(host.querySelector('select')?.disabled).toBe(true);
 await act(async()=>{cache.setQueryData(journeyKey('p'),{...state,active_card_id:'b'});await new Promise(resolve=>setTimeout(resolve,30));});
 expect(host.querySelector('select')?.value).toBe('a');expect(host.textContent).toContain('编辑 a');expect(command).not.toHaveBeenCalled();
 }finally{await act(async()=>root.unmount());cache.clear();host.remove();vi.restoreAllMocks();}
});

test('existing production is organized into a reviewable draft before entering a bound card',async()=>{
 const initial={project_id:'p',revision:1,initial_demo_direction:{direction_id:'d'},cards:[],versions:[]} as unknown as PlanningJourney;
 const organized={...initial,revision:2,production_basis:{task_id:'native',workspace_id:'current'},outline:{title:'现有游戏',experience:'保留玩法'},cards:[{id:'weapon',title:'武器与射击',description:'源码驱动',acceptance:'在原游戏中试玩',source_ids:['source-weapon']}]} as PlanningJourney;
 vi.spyOn(journeyClient,'get').mockResolvedValue(initial);
 const stream=vi.spyOn(journeyClient,'stream').mockResolvedValue(organized);
 const command=vi.spyOn(journeyClient,'command').mockResolvedValue({...organized,active_card_id:'weapon'});
 const open=vi.fn();const cache=new QueryClient({defaultOptions:{queries:{retry:false}}});
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 try {
  await act(async()=>root.render(<QueryClientProvider client={cache}><ProjectPlanningTools projectId="p" onOpenConversation={open}/></QueryClientProvider>));
  await act(async()=>{await new Promise(resolve=>setTimeout(resolve,30));});
  vi.mocked(journeyClient.get).mockResolvedValue(organized);
  await act(async()=>{Array.from(host.querySelectorAll('button')).find(button=>button.textContent==='基于当前版本整理策划')!.click();});
  await act(async()=>{await new Promise(resolve=>setTimeout(resolve,30));});
  expect(stream.mock.calls[0]?.[1].operation).toBe('organize_production');
  expect(open).toHaveBeenCalled();
  const enter=Array.from(host.querySelectorAll('button')).find(button=>button.textContent==='进入卡片 →')!;
  expect(enter.disabled).toBe(true);
  await act(async()=>{cache.setQueryData(journeyKey('p'),{...organized,versions:[{number:1}]});await new Promise(resolve=>setTimeout(resolve,30));});
  await act(async()=>enter.click());
  expect(command.mock.calls[0]?.[1].card_id).toBe('weapon');
 } finally {await act(async()=>root.unmount());cache.clear();host.remove();vi.restoreAllMocks();}
});
