import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getCodeBuddyModels, type CodeBuddyModel, type CodeBuddyConversationTransport } from '../conversation/CodeBuddyConversationTransport.ts';

export function ConversationModelPicker({ transport, disabled }: { transport: CodeBuddyConversationTransport; disabled: boolean }) {
  const [selected, setSelected] = useState(transport.selectedModel);
  const query = useQuery({ queryKey: ['conversation', 'codebuddy-models'], queryFn: ({ signal }) => getCodeBuddyModels(signal), retry: false, staleTime: 60000 });
  return <div className="conversation-model-picker">
    <label>对话模型 <select aria-label="对话模型" disabled={disabled} value={selected} onChange={event => {
      const model = event.target.value as 'mock' | CodeBuddyModel;
      transport.selectedModel = model;
      setSelected(model);
    }}><option value="mock">MOCK · 确定性演示</option>
      {query.data?.models.map(model => <option key={model.id} value={model.id} disabled={model.mode === 'blocked'}>CodeBuddy · {model.id}</option>)}
    </select></label>
    <small>{selected === 'mock' ? '不调用外部模型' : 'planned · 点击发送将通过 CodeBuddy CLI 请求所选模型'}</small>
    {query.isPending && <small>正在读取本地模型选项…</small>}
    {query.error && <small role="alert">BLOCKED · {query.error.message} <button onClick={() => void query.refetch()}>重试连接</button></small>}
    {query.data && !query.data.available && <small role="status">BLOCKED · {query.data.message}</small>}
  </div>;
}
