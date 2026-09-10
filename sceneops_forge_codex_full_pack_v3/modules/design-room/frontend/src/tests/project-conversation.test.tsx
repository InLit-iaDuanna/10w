import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {test, expect, vi} from 'vitest';
import {PlanningJourneyGate} from '../PlanningJourney';
import {journeyClient, type PlanningJourney, type JourneyCommand} from '../journey-client';
import {workspaceClient} from '../../../../../packages/workspace-client/frontend/src/index.ts';
Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
Object.defineProperty(HTMLElement.prototype,'scrollTo',{configurable:true,value:function(options:ScrollToOptions){this.scrollTop=options.top ?? 0;}});
const direction={core_experience:'收集星星返回基地',perspective_style:'俯视太空',simplified_scope:'单关',code_architecture:'object-component' as const,camera_mode:'fit-scene' as const};
for (const policy of ['ask','full-access'] as const) test(`single conversation start preserves ${policy} permission without cards`,async()=>{
 let state={project_id:'p',root_path:'/tmp/game',revision:1,stage:'idea',messages:[{id:'m',role:'assistant',text:'收集星星返回基地。',created_at:'2026-09-08T00:00:00Z',mode:'mock'}],cards:[],versions:[],collaboration:'solo',composer_draft:'',model_calls:0,cost_notice:'fixture',execution_policy:policy,demo_direction_draft:direction} as PlanningJourney;
 vi.spyOn(workspaceClient,'folderProjects').mockResolvedValue({projects:[{project_id:'p',project_kind:'sceneops_created'}]} as never);
 vi.spyOn(journeyClient,'get').mockImplementation(async()=>state);
 const command=vi.spyOn(journeyClient,'command').mockImplementation(async(_id:string,body:JourneyCommand)=>{
   expect(body.operation).toBe('confirm_demo_direction');
   state={...state,revision:2,initial_demo_direction:{...direction,target_platform:'web',direction_id:'direction_01234567890123456789012345678901',confirmed:true}};
   return state;
 });
 const prepare=vi.fn().mockResolvedValue(undefined);
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);const cache=new QueryClient({defaultOptions:{queries:{retry:false}}});
 try {
  await act(async()=>{root.render(<QueryClientProvider client={cache}><PlanningJourneyGate projectId="p" fallback={null} modelPicker={()=>null} onOpenProjects={()=>{}} development={{prepare:vi.fn(),prepareProjectDemo:prepare,renderTasks:()=>null}} /></QueryClientProvider>);});
  await act(async()=>{await new Promise(r=>setTimeout(r,40));});
  expect(host.textContent).not.toContain('确认初版方向');expect(host.textContent).not.toContain('四卡');
  expect(host.textContent).toContain(policy==='ask'?'执行前询问':'完全访问');
  expect(prepare).not.toHaveBeenCalled();
  const button=[...host.querySelectorAll('button')].find(b=>b.textContent==='开始制作');expect(button).toBeTruthy();
  await act(async()=>{button!.click();await new Promise(r=>setTimeout(r,40));});
  expect(command).toHaveBeenCalledTimes(1);expect(prepare).toHaveBeenCalledWith('p',expect.stringMatching(/^direction_/),expect.stringContaining('收集星星'),policy,false,[],undefined);
 } finally {await act(async()=>root.unmount());cache.clear();host.remove();vi.restoreAllMocks();}
});
