import {useState} from 'react';
import {useMutation,useQueryClient} from '@tanstack/react-query';
import {PRODUCTION_DOMAINS,type ProductionDomainId} from '../../../project-intake/frontend/src/index.ts';
import {journeyClient,journeyKey,type PlanningJourney} from './journey-client.ts';
import './production-domains.css';

const TOOLS:Record<ProductionDomainId,readonly [string,string][]>={
 planning:[['journey.progress','制作进度'],['harness.pipeline','AI 生产计划与能力']],
 'assets-animation':[['journey.modeling','模型与资产'],['asset.builtin-library','内置资产'],['workbench.character-animation','角色与动画制作'],['journey.source','动画源码与功能包']],
 world:[['journey.environment','编辑当前场景']],
 gameplay:[['workbench.world-logic','交互逻辑配置'],['journey.source','玩法源码与功能包']],
 lookdev:[['lookdev.material','AI 材质与 Shader'],['journey.environment','游戏场景灯光'],['workbench.render-ops','渲染与性能']],
 'ui-audio':[['workbench.ui-audio-vfx','界面、音频与特效工具'],['journey.source','界面与声音源码']],
 delivery:[['journey.game-preview','构建与试玩'],['workbench.ai-playtest','AI 游测配置'],['build.export','导出'],['workbench.version-review','版本管理']],
};
type Props={initialDomain?:ProductionDomainId;state:PlanningJourney;disabled?:boolean;onSelectCard:(id:string)=>void;onOpenTool?:(id:string)=>void;onRequestDevelopment?:(goal:string)=>void};
export function ProductionDomains({state,disabled,onSelectCard,onOpenTool,initialDomain,onRequestDevelopment}:Props){
 const [selected,setSelected]=useState<ProductionDomainId>(initialDomain??'planning');
 const cache=useQueryClient();
 const mutation=useMutation({mutationFn:(body:Parameters<typeof journeyClient.command>[1])=>journeyClient.command(state.project_id,body),onSuccess:next=>cache.setQueryData(journeyKey(state.project_id),next)});
 const domain=PRODUCTION_DOMAINS.find(item=>item.id===selected)!;
 const cards=state.cards??[];
 const linked=cards.filter(card=>card.domain_ids?.includes(selected));
 const unassigned=cards.filter(card=>!card.domain_ids?.length);
 return <section className="production-domains" aria-label="七个生产领域">
  <header><strong>统一生产领域</strong><p>每个游戏使用同样的七个领域。功能包可关联多个领域，继续使用原会话和项目对象。</p></header>
  <nav aria-label="生产领域">{PRODUCTION_DOMAINS.map(item=><button key={item.id} aria-pressed={selected===item.id} onClick={()=>setSelected(item.id)}><strong>{item.title}</strong><small>{item.description}</small></button>)}</nav>
  <article key={`${selected}/${state.revision}`}>
   <h3>{domain.title}</h3><p>{domain.description}</p>
   <DomainWorkForm value={state.domain_work?.[selected]} disabled={!!disabled||mutation.isPending} onSave={work=>mutation.mutate({operation:'save_domain',domain_id:selected,domain_work:work,request_id:crypto.randomUUID(),expected_revision:state.revision,text:'',accept_assumptions:false})}/>
   {onRequestDevelopment&&<button disabled={disabled||mutation.isPending} onClick={()=>onRequestDevelopment(`继续当前游戏的「${domain.title}」制作。领域键：${selected}。\n制作说明：${state.domain_work?.[selected]?.brief||'先读取当前项目并对齐本领域目标。'}\n关联功能包：${linked.map(card=>`${card.id}（${card.title}）`).join('、')||'尚未关联'}。\n复用已有项目、对象身份、源版本和制作会话；先读取资产、场景、材质文档与真实源码。使用本领域已接入的专业工具和已选择的制作技能。保存候选与应用分开，应用后重新构建试玩，记录实际结果。`)}>在主对话用 AI 制作此领域 →</button>}
   {onOpenTool&&<div className="production-domain-tools">{TOOLS[selected].map(([id,title])=><button key={id} onClick={()=>onOpenTool(id)}>{title} →</button>)}</div>}
   {(['assets-animation','gameplay','ui-audio'] as string[]).includes(selected)&&<p className="production-domain-note">模型使用已登记资产；动画、玩法、界面和声音的代码修改沿用原功能包会话，构建后试玩验证。</p>}
   <h4>关联功能包 · {linked.length}</h4>
   {linked.map(card=><div className="production-domain-package" key={card.id}><strong>{card.title}</strong><p>{card.description}</p><button disabled={disabled||!(state.versions??[]).length} onClick={()=>onSelectCard(card.id)}>进入原功能包 →</button></div>)}
   {!linked.length&&<p>此领域尚未关联功能包。专业工具仍使用当前项目的资产与场景。</p>}
   <details><summary>管理功能包关联{unassigned.length?` · ${unassigned.length} 个尚未归类`:''}</summary><p>勾选将现有功能包关联到「{domain.title}」，保留它的 ID、会话、任务与源码。</p>{cards.map(card=><label className="production-domain-assignment" key={card.id}><input type="checkbox" checked={card.domain_ids?.includes(selected)??false} disabled={disabled||mutation.isPending} onChange={e=>mutation.mutate({operation:'assign_card_domains',card_id:card.id,domain_ids:e.target.checked?[...(card.domain_ids??[]),selected]:(card.domain_ids??[]).filter(id=>id!==selected),request_id:crypto.randomUUID(),expected_revision:state.revision,text:'',accept_assumptions:false})}/>{card.title}</label>)}</details>
   {mutation.error&&<p role="alert">{mutation.error.message}</p>}
  </article>
 </section>;
}
type Work=NonNullable<PlanningJourney['domain_work']>[ProductionDomainId];
function DomainWorkForm({value,disabled,onSave}:{value:Work|undefined;disabled:boolean;onSave:(work:Work)=>void}){
 const [brief,setBrief]=useState(value?.brief??'');const [stage,setStage]=useState<Work['stage']>(value?.stage??'not-started');
 return <form onSubmit={e=>{e.preventDefault();onSave({brief,stage});}}><label>本领域制作说明<textarea value={brief} onChange={e=>setBrief(e.target.value)} disabled={disabled}/></label><label>制作阶段<select value={stage} onChange={e=>setStage(e.target.value as Work['stage'])} disabled={disabled}><option value="not-started">待开始</option><option value="graybox">草模与原型</option><option value="refinement">细化制作</option><option value="review">待试玩验收</option></select></label><button disabled={disabled}>保存制作说明</button></form>;
}
