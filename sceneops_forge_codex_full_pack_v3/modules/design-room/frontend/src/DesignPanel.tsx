import React, {useState} from 'react';
import type {ProjectIntakeRecord,DocumentVersion,FeatureSpec,DesignCommandMetadata} from './contracts.ts';
import {createDesignRoomRuntime} from './runtime.ts';
import {validateFeatureForPlanning} from './validation.ts';
const context={moduleEnabled:true,permissions:new Set(['design:read','design:write','design:approve'])};
const meta=(actorType:'user'|'assistant'='user'):DesignCommandMetadata=>({commandId:crypto.randomUUID(),eventId:crypto.randomUUID(),correlationId:crypto.randomUUID(),actorId:'user:local',actorType,occurredAt:new Date().toISOString(),mode:'mock'});
export function DesignPanel({intake,brief,onPlan}:{intake:ProjectIntakeRecord,brief:string,onPlan:(version:DocumentVersion<FeatureSpec>)=>Promise<void>}){
 const [runtime]=useState(createDesignRoomRuntime);
 const [version,setVersion]=useState(()=>runtime.commands.draftFeatureFromConversation(context,{
 featureSpecId:crypto.randomUUID(),projectId:intake.projectId,gddId:null,title:intake.fields.projectName.value||'新功能',goal:brief,playerValue:'玩家能理解目标并完成互动',
 inputs:[{id:'input:1',source:'player',statement:'玩家发起交互'}],outputs:[{id:'output:1',consumer:'player',statement:'目标状态变化并给予反馈'}],dependencies:[],
 edgeCases:[{id:'edge:1',statement:'前置条件不满足',expectedBehavior:'显示原因并保留当前状态'}],
 acceptanceCriteria:[{criterionId:'criterion:1',title:'主路径',given:'玩家处于可交互场景',when:'完成前置条件并发起交互',then:brief,priority:'must'}],
 requiredDeliverables:[{requirementId:'deliverable:1',kind:'script',description:'实现功能状态与交互反馈',existingArtifactId:null}],
 requiredTests:[{testId:'test:1',level:'playtest',description:'验证主路径及前置条件不足',linkedCriterionIds:['criterion:1']}],
 inferredStatements:[{id:'assumption:1',statement:'以上结构由本地固定模板生成，请逐项检查后确认。'}],sourceMessageId:'brief:local'
 },crypto.randomUUID(),meta('assistant')).version);
 const [draft,setDraft]=useState(version.document);const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [diff,setDiff]=useState('');
 const issues=validateFeatureForPlanning(draft,intake);
 function save(){const next=runtime.commands.saveFeature(context,{versionId:crypto.randomUUID(),document:{...draft,status:'draft'},rationale:'用户在结构化设计界面编辑。'},meta()).version;
 setDiff(runtime.diff('feature-spec',draft.featureSpecId,version.versionId,next.versionId).map(x=>`${x.kind} ${x.path}`).join('\n')||'没有字段变化');setVersion(next);setDraft(next.document);return next;}
 async function plan(){setBusy(true);setError('');try{save();const ready=runtime.commands.markFeatureReady(context,draft.featureSpecId,intake,crypto.randomUUID(),crypto.randomUUID(),meta()).version;setVersion(ready);setDraft(ready.document);await onPlan(ready)}catch(e){setError(String(e))}finally{setBusy(false)}}
 const criterion=draft.acceptanceCriteria[0];
 return <section><div className="section-title"><div><p className="eyebrow">02 / DESIGN ROOM</p><h2>设计规格</h2></div><span className="badge">mock · v{version.versionNumber} · {version.document.status}</span></div>
 <label>功能名称<input value={draft.title} onChange={e=>setDraft({...draft,title:e.target.value})}/></label>
 <label>目标<textarea rows={3} value={draft.goal} onChange={e=>setDraft({...draft,goal:e.target.value})}/></label>
 <label>玩家价值<input value={draft.playerValue} onChange={e=>setDraft({...draft,playerValue:e.target.value})}/></label>
 <div className="row"><label>输入<input value={draft.inputs[0].statement} onChange={e=>setDraft({...draft,inputs:[{...draft.inputs[0],statement:e.target.value}]})}/></label><label>输出<input value={draft.outputs[0].statement} onChange={e=>setDraft({...draft,outputs:[{...draft.outputs[0],statement:e.target.value}]})}/></label></div>
 <h3>验收标准 / Given · When · Then</h3>
 {(['given','when','then'] as const).map(key=><label key={key}>{({given:'前提',when:'操作',then:'预期结果'})[key]}<input value={criterion[key]} onChange={e=>setDraft({...draft,acceptanceCriteria:[{...criterion,[key]:e.target.value}]})}/></label>)}
 <div className="row"><label>边界情况<input value={draft.edgeCases[0].statement} onChange={e=>setDraft({...draft,edgeCases:[{...draft.edgeCases[0],statement:e.target.value}]})}/></label><label>预期处理<input value={draft.edgeCases[0].expectedBehavior} onChange={e=>setDraft({...draft,edgeCases:[{...draft.edgeCases[0],expectedBehavior:e.target.value}]})}/></label></div>
 <label>所需交付物<input value={draft.requiredDeliverables[0].description} onChange={e=>setDraft({...draft,requiredDeliverables:[{...draft.requiredDeliverables[0],description:e.target.value}]})}/></label>
 <label>测试要求（planned，未执行）<input value={draft.requiredTests[0].description} onChange={e=>setDraft({...draft,requiredTests:[{...draft.requiredTests[0],description:e.target.value}]})}/></label>
 <label className="checkbox"><input type="checkbox" checked={draft.assumptions[0].status==='confirmed'} onChange={e=>setDraft({...draft,assumptions:[{...draft.assumptions[0],status:e.target.checked?'confirmed':'unconfirmed'}]})}/>我已检查模板推断，确认以上设计内容</label>
 {issues.length>0&&<p className="notice">{issues.map(x=>x.message).join('；')}</p>}
 <div className="row"><button className="secondary" onClick={()=>{try{save();setError('')}catch(e){setError(String(e))}}}>保存设计版本</button><button disabled={busy||issues.length>0} onClick={plan}>{busy?'正在创建…':'确认设计 → 创建生产计划'}</button></div>
 {diff&&<details><summary>最近版本差异</summary><pre>{diff}</pre></details>}{error&&<p role="alert" className="error">{error}</p>}
 </section>
}
