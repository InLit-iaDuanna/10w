import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { aiKeys, saveSettings, type AISettings, type AISettingsUpdate } from './aiClient.ts';

type Provider = 'codebuddycli' | 'openai-compatible';
type ProviderSettings = AISettings;
type ProviderUpdate = AISettingsUpdate;

/** A write-only provider configuration surface. Secret input is never sent to TanStack MutationCache. */
export function ModelProviderSettings({ settings, disabled = false, compact = false }: { settings: AISettings; disabled?: boolean; compact?: boolean }) {
  const cache = useQueryClient();
  const current: ProviderSettings = settings;
  const [open, setOpen] = useState(false);
  const [provider, setProvider] = useState<Provider>(current.provider ?? 'codebuddycli');
  const [model, setModel] = useState(current.model);
  const [baseUrl, setBaseUrl] = useState(current.base_url ?? '');
  const [apiKey, setApiKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {if(open && dialog.current && !dialog.current.open) dialog.current.showModal();},[open]);
  useEffect(() => {
    if (!open) return;
    setProvider(current.provider ?? 'codebuddycli');
    setModel(current.model);
    setBaseUrl(current.base_url ?? '');
    setApiKey('');
    setError('');
  }, [open, current.provider, current.model, current.base_url]);
  const compatible = provider === 'openai-compatible';
  const endpointChanged = compatible && baseUrl.trim() !== (current.base_url ?? '').trim();
  const valid = !!model.trim() && (!compatible || !!baseUrl.trim());
  function changeProvider(nextProvider: Provider) {
    setProvider(nextProvider);
    setModel(nextProvider === 'codebuddycli' ? 'cli-default' : '');
    setApiKey('');
    setError('');
  }
  async function submit() {
    if (!valid || saving) return;
    const next: ProviderUpdate = { provider, model: model.trim() };
    if (compatible) next.base_url = baseUrl.trim();
    if (apiKey) next.api_key = apiKey;
    setSaving(true); setError('');
    try {
      const value = await saveSettings(next);
      cache.setQueryData(aiKeys.settings, value);
      void cache.invalidateQueries({ queryKey: aiKeys.models });
      setApiKey('');
      setOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally { setSaving(false); }
  }
  return <>
    <button className={`unified-ai-provider-button${compact ? ' is-icon' : ''}`} aria-label="模型与提供方设置" title="模型与提供方设置" type="button" disabled={disabled} onClick={() => setOpen(true)}><svg aria-hidden="true" viewBox="0 0 16 16"><path d="M8 2.2a1.4 1.4 0 0 1 1.3.9l.2.5c.3.1.6.3.9.5l.6-.1a1.4 1.4 0 0 1 1.5.7l.5.8a1.4 1.4 0 0 1-.2 1.6l-.4.4v1l.4.4a1.4 1.4 0 0 1 .2 1.6l-.5.8a1.4 1.4 0 0 1-1.5.7l-.6-.1-.9.5-.2.5a1.4 1.4 0 0 1-1.3.9h-1a1.4 1.4 0 0 1-1.3-.9l-.2-.5-.9-.5-.6.1a1.4 1.4 0 0 1-1.5-.7l-.5-.8a1.4 1.4 0 0 1 .2-1.6l.4-.4v-1l-.4-.4A1.4 1.4 0 0 1 2 5.5l.5-.8A1.4 1.4 0 0 1 4 4l.6.1.9-.5.2-.5A1.4 1.4 0 0 1 7 2.2h1Z"/><circle cx="7.5" cy="8" r="1.8"/></svg>{!compact && '提供方'}</button>
    {open && <dialog ref={dialog} className="unified-ai-provider-dialog" aria-label="AI 提供方设置" onCancel={event=>{event.preventDefault();if(!saving){setApiKey('');setOpen(false);}}}>
      <header><div><span className="tool-kicker">AI 连接</span><h2>模型与提供方</h2><p>配置只在保存后生效，不会在这里探测网络或验证密钥。</p></div><button type="button" aria-label="关闭设置" onClick={() => { setApiKey(''); setOpen(false); }}><svg aria-hidden="true" viewBox="0 0 16 16"><path d="m4 4 8 8M12 4l-8 8"/></svg></button></header>
      <div className="unified-ai-provider-note"><i aria-hidden="true" /><span>当前配置</span><strong>{current.provider === 'openai-compatible' ? 'OpenAI 兼容服务' : 'CodeBuddy CLI'}</strong><small>{current.model}</small></div>
      <div className="unified-ai-provider-fields">
        <label><span>提供方</span><select value={provider} disabled={saving} onChange={event => changeProvider(event.target.value as Provider)}><option value="codebuddycli">CodeBuddy CLI</option><option value="openai-compatible">OpenAI 兼容服务</option></select></label>
        <label><span>模型 {compatible && <em>必填</em>}</span><input value={model} disabled={saving} placeholder={compatible ? '输入兼容服务的模型 ID' : 'cli-default'} onChange={event => setModel(event.target.value)} /></label>
      </div>
      {compatible && <div className="unified-ai-provider-fields unified-ai-provider-advanced">
        <div className="unified-ai-provider-section-title"><span>兼容服务连接</span><small>密钥与完整服务地址绑定</small></div>
        <label><span>服务地址 <em>必填</em></span><input type="url" value={baseUrl} disabled={saving} placeholder="https://provider.example/v1" onChange={event => setBaseUrl(event.target.value)} /><small>仅保存明确填写的地址；不会自动探测服务。</small></label>
        <label><span>API Key <em>只写 · 可选</em></span><input type="password" value={apiKey} autoComplete="new-password" disabled={saving} placeholder={endpointChanged ? '新地址未填写密钥；保存后将显示未配置' : current.api_key_configured ? '当前地址已配置；留空保持不变' : '输入后只写入，不会再次显示'} onChange={event => setApiKey(event.target.value)} /><small>{endpointChanged ? '新地址没有提供密钥时，将显示为未配置。' : current.api_key_configured ? '当前地址已有密钥；仅输入新值时替换。' : '此地址尚未配置密钥，只随本次保存请求发送。'}</small></label>
      </div>}
      {error && <p role="alert">保存失败：{error}。当前输入仍保留，可修改后重试。</p>}
      <footer><button type="button" onClick={() => { setApiKey(''); setOpen(false); }} disabled={saving}>取消</button><button className="unified-ai-save-provider" type="button" onClick={() => void submit()} disabled={saving || !valid}>{saving ? '保存中…' : '保存设置'}</button></footer>
    </dialog>}
  </>;
}
