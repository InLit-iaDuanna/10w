import type {ProductionDomainId} from '../../../project-intake/frontend/src/index.ts';
import {useCallback,useEffect,useState, type ReactNode} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {journeyClient,journeyKey} from './journey-client';
import './project-planning-tools.css';
import {ProductionDomains} from './ProductionDomains.tsx';
import {OrganizeProductionButton} from './OrganizeProductionButton';

type Props={initialDomain?:ProductionDomainId;projectId:string|null;onOpenConversation:()=>void;onOpenTool?:(id:string)=>void;onRequestDevelopment?:(goal:string)=>void;renderSource?:(cardId:string,onDirty:(value:boolean)=>void)=>ReactNode;onDirtyChange?:(value:boolean)=>void};
export function ProjectPlanningTools({projectId,...props}:Props) {
 if(!projectId)return <div className="project-tool-empty"><strong>先选择一个项目</strong><p>从右上角项目菜单打开游戏工程。</p></div>;
 return <PlanningContent key={projectId} projectId={projectId} {...props}/>;
}
function PlanningContent({projectId,onOpenConversation,onOpenTool,renderSource,onDirtyChange,initialDomain,onRequestDevelopment}:Props&{projectId:string}) {
 const cache=useQueryClient();const [chosen,setChosen]=useState<string|null>(null);const [dirty,setDirty]=useState(false);
 const sourceDirty=useCallback((value:boolean)=>{setDirty(value);onDirtyChange?.(value);},[onDirtyChange]);
 const query=useQuery({queryKey:journeyKey(projectId),queryFn:({signal})=>journeyClient.get(projectId,signal),retry:false});
 const defaultCard=query.data?.card_branches?.find(item=>item.card_id===query.data?.active_card_id)?.card_id??query.data?.card_branches?.[0]?.card_id;
 useEffect(()=>{if(chosen===null&&defaultCard)setChosen(defaultCard);},[chosen,defaultCard]);
 const select=useMutation({mutationFn:async(cardId:string)=>{
  const state=query.data;if(!state)throw new Error('策划尚未读取');
  return journeyClient.command(projectId,{operation:'select_card',card_id:cardId,request_id:crypto.randomUUID(),expected_revision:state.revision,text:'',accept_assumptions:false,context_draft:state.composer_draft??''});
 },onSuccess:state=>{cache.setQueryData(journeyKey(projectId),state);onOpenConversation();}});
 const prepareDomain=useMutation({mutationFn:async(goal:string)=>{
  const state=query.data;if(!state)throw new Error('策划尚未读取');
  if(state.active_card_id){const next=await journeyClient.command(projectId,{operation:'clear_card',request_id:crypto.randomUUID(),expected_revision:state.revision,text:'',accept_assumptions:false,context_draft:state.composer_draft??''});cache.setQueryData(journeyKey(projectId),next);}
  onRequestDevelopment?.(goal);
 }});
 if(query.isPending)return <div className="project-tool-empty" role="status">读取项目策划…</div>;
 if(query.error||!query.data)return <div className="project-tool-empty" role="alert"><p>{query.error?.message??'读取失败'}</p><button onClick={()=>void query.refetch()}>重新读取</button></div>;
 const state=query.data;const branches=state.card_branches??[];const cards=state.cards??[];
 const active=chosen??(branches.some(item=>item.card_id===state.active_card_id)?state.active_card_id:branches[0]?.card_id);
 return <section className={`project-planning-tool ${renderSource?'is-source-tool':''}`}>
  <header><div><small>{state.root_path?.split('/').at(-1)??'当前项目'}</small><h2>{renderSource?'架构与源码':'策划与制作卡片'}</h2></div><span>{state.technical_plan?.architecture_label??'技术方案待确认'}</span></header>
  {renderSource && state.production_basis ? <div className="project-plan-scroll"><p>制作卡片关联当前游戏工程，进入卡片可查看实际源码并继续修改。</p>{cards.map(card=><article className="project-plan-card" key={card.id}><div><h3>{card.title}</h3><p>{(card.source_ids ?? []).length} 个关联源码文件</p></div><button disabled={select.isPending || !(state.versions ?? []).length} onClick={()=>select.mutate(card.id)}>查看关联源码与对话 →</button></article>)}{select.error&&<p role="alert">{select.error.message}</p>}</div> : renderSource ? <>
   <div className="project-tool-selector"><label>当前制作卡片<select aria-label="源码卡片" value={active??''} disabled={dirty||!branches.length} onChange={event=>setChosen(event.target.value)}>{!branches.length&&<option value="">暂无登记工程</option>}{branches.map(branch=><option key={branch.card_id} value={branch.card_id}>{cards.find(card=>card.id===branch.card_id)?.title??branch.card_id}</option>)}</select></label><small>{dirty?'请先保存或放弃文件修改':'文件修改只作用于所选卡片工程'}</small></div>
   {active?renderSource(active,sourceDirty):<div className="project-tool-empty"><strong>还没有卡片工程</strong><p>先进入制作卡片，完成工程准备。</p><button onClick={onOpenConversation}>打开策划对话</button></div>}
  </>:<div className="project-plan-scroll">
   <ProductionDomains {...(onRequestDevelopment?{onRequestDevelopment:(goal:string)=>prepareDomain.mutate(goal)}:{})} {...(initialDomain?{initialDomain}:{})} state={state} onSelectCard={id=>select.mutate(id)} {...(onOpenTool?{onOpenTool}:{})} disabled={select.isPending||prepareDomain.isPending}/>{prepareDomain.error&&<p role="alert">{prepareDomain.error.message}</p>}<OrganizeProductionButton state={state} disabled={select.isPending} onComplete={onOpenConversation} />
   {state.production_basis && !(state.versions ?? []).length && <p role="status">策划与卡片为待审阅草稿，请在主对话中确认策划后进入制作。</p>}
   <section className="project-plan-overview"><small>当前大纲</small><h3>{state.outline?.title??'大纲尚未生成'}</h3><p>{state.outline?.experience??'在主对话中确认游戏想法、范围与技术方案。'}</p><details><summary>完整大纲</summary><h3>核心循环</h3><p>{state.outline?.core_loop}</p><h3>制作范围</h3><p>{state.outline?.scope}</p><h3>验收要求</h3><p>{state.outline?.acceptance}</p><p>{state.outline?.assumptions?.join('\n')}</p></details><button onClick={onOpenConversation}>继续策划对话 →</button></section>
   <div className="project-plan-section-title"><strong>项目功能包</strong><small>{cards.length} 个功能包</small></div>
   {cards.map((card,i)=><article className="project-plan-card" key={card.id}><span className="project-card-number">{String(i+1).padStart(2,'0')}</span><div><h3>{card.title}</h3><p>{card.description}</p><details><summary>内容、完成条件与依赖</summary><p>{card.description}</p><p>{card.acceptance}</p><small>{(card.dependencies??[]).map(id=>cards.find(item=>item.id===id)?.title??id).join(' · ')||'无前置卡片'}</small></details></div><button disabled={select.isPending || !(state.versions ?? []).length} onClick={()=>select.mutate(card.id)}>进入卡片 →</button></article>)}
   {!cards.length&&<p>确认策划大纲后，制作卡片会显示在这里。</p>}
   {select.error&&<p role="alert">{select.error.message}</p>}
  </div>}
 </section>;
}
