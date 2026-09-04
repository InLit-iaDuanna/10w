import React, {useState} from 'react';
import {createProjectIntakeRuntime} from './runtime.ts';
import {DeterministicProjectScanAdapter} from './adapters/ProjectScanAdapter.ts';
import {warehouseEscapeScanReport} from './fixtures/projects.ts';
import type {ProjectIntakeRecord} from './contracts.ts';
const context = {moduleEnabled:true, permissions:new Set(['project:read','project:write','project:scan'])};
const metadata = () => ({commandId:crypto.randomUUID(),eventId:crypto.randomUUID(),correlationId:crypto.randomUUID(),actorId:'user:local',occurredAt:new Date().toISOString()});
export function IntakePanel({onReady}:{onReady:(record:ProjectIntakeRecord,brief:string)=>void}) {
 const [runtime] = useState(()=>createProjectIntakeRuntime(new Map([[warehouseEscapeScanReport.adapterId,new DeterministicProjectScanAdapter({status:'online',checkedAt:warehouseEscapeScanReport.scannedAt,message:'隔离示例扫描'},warehouseEscapeScanReport)]])));
 const [name,setName]=useState('归途 · 钥匙与家门'); const [brief,setBrief]=useState('玩家在走廊找到钥匙，拾取后打开家门；没有钥匙时显示提示。');
 const [platform,setPlatform]=useState('Windows'); const [path,setPath]=useState('/demo/find-my-way-home');
 const [record,setRecord]=useState<ProjectIntakeRecord|null>(null); const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 async function create(scan=false){setError('');setBusy(true);try{
  const meta=metadata(); const root={rootId:crypto.randomUUID(),kind:'workspace' as const,absolutePath:path,displayName:name};
  const common={intakeId:crypto.randomUUID(),projectId:crypto.randomUUID(),actorId:meta.actorId,occurredAt:meta.occurredAt};
  const result=scan ? await runtime.commands.scanExisting(context,{...common,projectRoot:root,adapterId:warehouseEscapeScanReport.adapterId},meta) : runtime.commands.createFromConversation(context,{...common,projectName:name,targetPlatforms:[platform],projectRoots:[root],mode:'mock',sourceMessageId:meta.commandId},meta);
  setRecord(result.record);
 }catch(e){setError(String(e))}finally{setBusy(false)}}
 function confirm(){if(!record)return;try{let next=runtime.commands.confirmField(context,{intakeId:record.intakeId,field:'projectName',value:name},metadata()).record;
 next=runtime.commands.confirmField(context,{intakeId:record.intakeId,field:'targetPlatforms',value:[platform]},metadata()).record;
 next=runtime.commands.confirmField(context,{intakeId:record.intakeId,field:'projectRoots',value:[{rootId:record.fields.projectRoots.value?.[0]?.rootId||crypto.randomUUID(),kind:'workspace',absolutePath:path,displayName:name}]},metadata()).record;
 setRecord(next); if(next.status!=='ready')throw Error('请填写名称、平台与绝对路径');onReady(next,brief);
 }catch(e){setError(String(e))}}
 return <section className="intake"><p className="eyebrow">01 / PROJECT INTAKE</p><h1>把一个想法，变成可执行的计划。</h1><p className="muted">从 brief 开始，逐项确认设计，再编排生产。所有数据仅在本次隔离会话中。</p>
 <label>项目名称<input value={name} onChange={e=>setName(e.target.value)}/></label>
 <label>项目 brief<textarea rows={4} value={brief} onChange={e=>setBrief(e.target.value)}/></label>
 <div className="row"><label>目标平台<input value={platform} onChange={e=>setPlatform(e.target.value)}/></label><label>项目目录（仅记录，不读写）<input value={path} onChange={e=>setPath(e.target.value)}/></label></div>
 <div className="row"><button disabled={busy||!brief.trim()} onClick={()=>create()}>从 brief 创建草稿</button><button disabled={busy} className="secondary" onClick={()=>create(true)}>导入仓库逃脱扫描示例 · mock</button></div>
 {record&&<div className="notice"><strong>入口：{record.status} · {record.mode}</strong><p>名称 {record.fields.projectName.confidence} · 平台 {record.fields.targetPlatforms.confidence} · 目录 {record.fields.projectRoots.confidence}</p>{record.scanReference&&<p>扫描：{record.scanReference.adapterId} · {record.scanReference.warnings.join('；')}。上方输入将作为你的明确确认值。</p>}<button onClick={confirm}>确认名称、平台和目录 → 编辑设计</button></div>}
 {error&&<p role="alert" className="error">{error}</p>}<p className="muted">扫描适配器：mock；真实 Unity / Blender 扫描：blocked（未连接）。</p></section>
}
