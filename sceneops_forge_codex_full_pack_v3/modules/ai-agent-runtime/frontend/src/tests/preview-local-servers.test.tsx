import React,{act,useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {test,expect,vi} from 'vitest';
import {agentTasks,type AgentTask} from '../client';
import {NativeDemoPreview} from '../DemoWorkbench';
import {ProjectGameTool} from '../ProjectGameTools';
import {LocalServerPanel} from '../LocalServerPanel';
import {localServers} from '../local-server-client';
import {workspaceClient} from '../../../../../packages/workspace-client/frontend/src/index.ts';
vi.mock('../AgentTaskWorkbench',()=>({AgentTaskTimeline:()=>null,AgentTaskActivity:()=>null,TaskCard:()=>null,
 GameRuntimePanel:({task,onPreviewChange}:any)=>{useEffect(()=>onPreviewChange(`http://127.0.0.1:6000/${task.id}`),[task.id,onPreviewChange]);return null;}}));
Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
async function mount(element:React.ReactNode){const cache=new QueryClient({defaultOptions:{queries:{retry:false}}});const host=document.createElement('div');document.body.append(host);const root=createRoot(host);await act(async()=>{root.render(<QueryClientProvider client={cache}>{element}</QueryClientProvider>);await new Promise(r=>setTimeout(r,20));});await act(async()=>{await new Promise(r=>setTimeout(r,20));});return {host,close:async()=>{await act(async()=>root.unmount());cache.clear();host.remove();vi.restoreAllMocks();}};}
test('chat preview delegates to dock without opening a new window',async()=>{
 vi.spyOn(agentTasks,'gameStatus').mockResolvedValue({preview:{status:'running',preview_url:'http://127.0.0.1:6000/',source_stale:false}} as never);
 const open=vi.spyOn(window,'open').mockImplementation(()=>null),dock=vi.fn();
 const ui=await mount(<NativeDemoPreview task={{id:'t',grant:{}} as AgentTask} onOpenPreview={dock}/>);
 try {await act(async()=>ui.host.querySelector('button')!.click());expect(dock).toHaveBeenCalledWith({taskId:'t',url:'http://127.0.0.1:6000/'});expect(open).not.toHaveBeenCalled();}finally{await ui.close();}
});
test('side preview selects requested task and offers explicit popout',async()=>{
 vi.spyOn(agentTasks,'list').mockResolvedValue({tasks:[{id:'new',created_at:'2026-09-08',grant:{},goal:'new',authorization_card:{allow_game_execution:true}},{id:'chosen',created_at:'2026-09-07',grant:{},goal:'chosen',authorization_card:{allow_game_execution:true}}]} as never);
 const ui=await mount(<ProjectGameTool projectId="p" preferredTaskId="chosen"/>);
 try {expect(ui.host.querySelector('iframe')?.getAttribute('src')).toBe('http://127.0.0.1:6000/chosen');const link=ui.host.querySelector('a');expect(link?.textContent).toContain('单独弹出');expect(link?.target).toBe('_blank');}finally{await ui.close();}
});
test('server stop requires selecting and confirming one eligible service',async()=>{
 vi.spyOn(workspaceClient,'projects').mockResolvedValue({projects:[]} as never);
 vi.spyOn(localServers,'list').mockResolvedValue({observed_at:'2026-09-08',servers:[{id:'s',name:'node',pid:10,endpoints:[{host:'127.0.0.1',port:6000}],can_stop:true},{id:'protected',name:'system',pid:11,endpoints:[{host:'*',port:7000}],can_stop:false,stop_reason:'系统服务，仅供查看'}]} as never);
 const stop=vi.spyOn(localServers,'stop').mockResolvedValue({id:'s',state:'stopped',remaining_endpoints:[],message:'该服务已不再监听。'});
 const ui=await mount(<LocalServerPanel/>);
 try {const buttons=()=>[...ui.host.querySelectorAll('button')];expect(buttons().filter(b=>b.textContent==='关闭服务')).toHaveLength(1);await act(async()=>buttons().find(b=>b.textContent==='关闭服务')!.click());expect(stop).not.toHaveBeenCalled();await act(async()=>buttons().find(b=>b.textContent==='确认关闭')!.click());expect(stop).toHaveBeenCalledWith('s');expect(ui.host.textContent).toContain('该服务已不再监听');}finally{await ui.close();}
});
