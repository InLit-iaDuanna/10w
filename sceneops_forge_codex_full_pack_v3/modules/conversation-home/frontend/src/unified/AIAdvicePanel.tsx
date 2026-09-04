import { useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { WorkbenchContext } from '@sceneops/core-ui';
import { requestAdvice, type AIModuleDocument } from './aiClient.ts';
import { UnifiedModelPicker, useAIAvailability } from './UnifiedModelPicker.tsx';
import './unified-ai.css';

type AdviceProps = { context: WorkbenchContext; moduleId: string; moduleDocument?: AIModuleDocument; onDirtyChange?: (dirty: boolean) => void };
export function AIAdvicePanel(props: AdviceProps) {
  return <AdviceForm key={`${props.context.projectId ?? 'pre_project'}:${props.moduleId}`} {...props} />;
}

function AdviceForm({ context, moduleId, moduleDocument, onDirtyChange }: AdviceProps) {
  const [prompt, setPrompt] = useState('');
  const [cancelled, setCancelled] = useState(false);
  const [includeDocument, setIncludeDocument] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const { ready } = useAIAvailability();
  const advice = useMutation({ mutationFn: () => {
    controller.current = new AbortController(); setCancelled(false);
    return requestAdvice(prompt.trim(), moduleId, context, controller.current.signal, includeDocument ? moduleDocument : undefined);
  }, onSuccess: () => setPrompt('') });
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => { onDirtyChange?.(!!prompt.trim() || advice.isPending); }, [prompt, advice.isPending, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);
  return <details className="unified-ai-advice"><summary>AI 模块建议 · CodeBuddy</summary>
    <UnifiedModelPicker disabled={advice.isPending} />
    <p>发送所选项目及对象 ID 和你的问题；勾选后才附带草稿。建议不会自动应用、审批或执行。</p>
    <label><input type="checkbox" checked={includeDocument} disabled={!moduleDocument || advice.isPending}
      onChange={event => setIncludeDocument(event.target.checked)} />附带当前已保存草稿</label>
    <form onSubmit={(event) => { event.preventDefault(); if (prompt.trim() && ready && !advice.isPending) advice.mutate(); }}>
      <textarea aria-label="向当前模块提问" value={prompt} maxLength={16000} disabled={advice.isPending}
        placeholder="需要 AI 帮你分析什么？" onChange={(event) => setPrompt(event.target.value)} />
      {advice.isPending ? <button type="button" onClick={() => { setCancelled(true); controller.current?.abort(); }}>取消</button>
        : <button type="submit" disabled={!prompt.trim() || !ready}>获取建议</button>}
    </form>
    {advice.isPending && <p role="status">正在生成建议…</p>}
    {cancelled && !advice.isPending && <p role="status">已取消。</p>}
    {advice.error && !cancelled && <p role="alert">{advice.error.message} <button disabled={!ready}
      onClick={() => advice.mutate()}>重试</button></p>}
    {advice.data && <article><small>live · {advice.data.model} · 待人工采用</small><p>{advice.data.text}</p></article>}
  </details>;
}
