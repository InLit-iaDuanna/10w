import React, {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import type {AiRequest, AiResult, ModelCatalog} from './generated/ai-contracts.ts';
import type {DesignChangeSet, FeatureSpec} from './contracts.ts';
import {structuralDiff} from './structuralDiff.ts';

export interface DesignAiClient {
  aiModels(): Promise<ModelCatalog>;
  aiSuggest(input: AiRequest): Promise<AiResult>;
}

export function DesignAiControls({client, busy, proposal, result, onGenerate, onApprove, onDiscard}: {
  client: DesignAiClient;
  busy: boolean;
  proposal: DesignChangeSet<FeatureSpec> | null;
  result: AiResult | null;
  onGenerate(model: string): Promise<void>;
  onApprove(): void;
  onDiscard(): void;
}) {
  const [model, setModel] = useState('');
  const models = useQuery({queryKey:['design-room','codebuddy-models'], queryFn:()=>client.aiModels(), retry:false});
  return <div className="notice">
    <h3>AI 设计建议 · CodeBuddy CLI</h3>
    <p>选择模型后，只将 brief 与当前六个设计字段发送给 CodeBuddy。建议先展示差异，批准后写入设计草稿。</p>
    {models.isPending ? <p>正在读取本机模型列表…</p> : models.error ?
      <p role="alert">模型读取失败：{models.error.message}</p> :
      <p>{models.data?.mode} · {models.data?.message}</p>}
    <div className="row">
      <label>AI 模型<select value={model} disabled={busy} onChange={event=>setModel(event.target.value)}>
        <option value="">请选择模型</option>
        {(models.data?.models||[]).map(id=><option key={id} value={id}>{id}</option>)}
      </select></label>
      <button className="secondary" disabled={busy||models.isFetching} onClick={()=>models.refetch()}>重新读取模型</button>
      <button disabled={busy||!models.data?.models.includes(model)||Boolean(proposal)} onClick={()=>onGenerate(model)}>
        {busy?'CodeBuddy 正在生成…':'生成设计建议'}
      </button>
    </div>
    {result&&<p>建议来源：{result.provider} · {result.model} · {result.mode} · {result.created_at}</p>}
    {proposal&&<div>
      <h4>待批准的设计变更</h4>
      <p>{proposal.rationale} · 基于版本 {proposal.baseVersionId}</p>
      {structuralDiff(proposal.previousValue,proposal.proposedValue).map(item=><div key={item.path} className="ai-diff">
        <strong>{item.path}</strong><p>原值：{String(item.before ?? '无')}</p><p>建议：{String(item.after ?? '无')}</p>
      </div>)}
      <div className="row"><button onClick={onApprove}>批准并应用建议</button><button className="secondary" onClick={onDiscard}>放弃建议</button></div>
    </div>}
  </div>;
}
