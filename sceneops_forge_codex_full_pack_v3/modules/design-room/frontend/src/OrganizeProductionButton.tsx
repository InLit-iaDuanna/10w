import {useEffect,useRef,useState} from 'react';
import {useMutation,useQueryClient} from '@tanstack/react-query';
import {journeyClient,journeyKey,type PlanningJourney} from './journey-client';

export function OrganizeProductionButton({state,disabled=false,onComplete}:{state:PlanningJourney;disabled?:boolean;onComplete?:()=>void}) {
 const cache=useQueryClient();const controller=useRef<AbortController|null>(null);const [status,setStatus]=useState('');
 useEffect(()=>()=>controller.current?.abort(),[]);
 const organize=useMutation({mutationKey:['organize-production',state.project_id],mutationFn:()=>{
  controller.current=new AbortController();setStatus('读取当前工程并整理策划…');
  return journeyClient.stream(state.project_id,{operation:'organize_production',request_id:crypto.randomUUID(),expected_revision:state.revision,text:'',accept_assumptions:false},event=>{
   if(event.type==='status')setStatus(event.text);
  },controller.current.signal);
 },onSuccess:next=>{cache.setQueryData(journeyKey(state.project_id),next);onComplete?.();},onSettled:()=>cache.invalidateQueries({queryKey:journeyKey(state.project_id)})});
 if(!state.initial_demo_direction || (!state.production_basis && (state.cards ?? []).length>0))return null;
 return <section className="journey-production-start" aria-label="从初版进入分项制作">
  <p>基于已有工程整理策划与制作卡片，保留当前游戏和制作会话。生成结果先供审阅。</p>
  <button type="button" disabled={disabled||organize.isPending} onClick={()=>organize.mutate()}>{organize.isPending?status:state.production_basis?'根据当前版本重新整理策划':'基于当前版本整理策划'}</button>
  {organize.isPending&&<button type="button" onClick={()=>controller.current?.abort()}>停止整理</button>}
  {organize.error&&<p role="alert">{organize.error.message}</p>}
 </section>;
}
