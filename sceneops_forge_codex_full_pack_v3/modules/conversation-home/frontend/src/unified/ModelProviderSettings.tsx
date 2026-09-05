import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { aiKeys, saveSettings, type AISettings, type AISettingsUpdate } from './aiClient.ts';

type Provider = 'codebuddycli' | 'openai-compatible';
type ProviderSettings = AISettings;
type ProviderUpdate = AISettingsUpdate;

/** A write-only provider configuration surface. Secret input is never sent to TanStack MutationCache. */
export function ModelProviderSettings({ settings, disabled = false }: { settings: AISettings; disabled?: boolean }) {
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
    <button className="unified-ai-provider-button" type="button" disabled={disabled} onClick={() => setOpen(true)}>提供方设置</button>
    {open && <dialog ref={dialog} className="unified-ai-provider-dialog" aria-label="AI 提供方设置" onCancel={event=>{event.preventDefault();if(!saving){setApiKey('');setOpen(false);}}}>
      <header><div><span className="tool-kicker">AI PROVIDER</span><h2>模型与提供方</h2><p>保存后才更新配置；此处不会主动探测网络或验证密钥。</p></div><button type="button" aria-label="关闭设置" onClick={() => { setApiKey(''); setOpen(false); }}>×</button></header>
      <div className="unified-ai-provider-fields">
        <label>提供方<select value={provider} disabled={saving} onChange={event => changeProvider(event.target.value as Provider)}><option value="codebuddycli">CodeBuddy CLI</option><option value="openai-compatible">OpenAI 兼容服务</option></select></label>
        <label>模型{compatible && <em>必填</em>}<input value={model} disabled={saving} placeholder={compatible ? '输入兼容服务的模型 ID' : 'cli-default'} onChange={event => setModel(event.target.value)} /></label>
      </div>
      {compatible && <div className="unified-ai-provider-fields unified-ai-provider-advanced">
        <label>服务地址 <em>必填</em><input type="url" value={baseUrl} disabled={saving} placeholder="https://provider.example/v1" onChange={event => setBaseUrl(event.target.value)} /><small>仅保存明确填写的地址；不会自动探测服务。</small></label>
        <label>该地址的 API Key（可选）<input type="password" value={apiKey} autoComplete="new-password" disabled={saving} placeholder={endpointChanged ? '新地址未填写密钥；保存后将显示未配置' : current.api_key_configured ? '当前地址已配置；留空保持不变' : '只写入，不会再次显示'} onChange={event => setApiKey(event.target.value)} /><small>{endpointChanged ? '密钥按服务地址保存。新地址没有提供密钥时，将显示为未配置。' : current.api_key_configured ? '当前服务地址已配置密钥；输入新值才会替换。' : '此地址尚未配置密钥。密钥只随本次保存请求发送。'}</small></label>
      </div>}
      {error && <p role="alert">保存失败：{error}。当前输入仍保留，可修改后重试。</p>}
      <footer><button type="button" onClick={() => { setApiKey(''); setOpen(false); }} disabled={saving}>取消</button><button className="unified-ai-save-provider" type="button" onClick={() => void submit()} disabled={saving || !valid}>{saving ? '保存中…' : '保存设置'}</button></footer>
    </dialog>}
  </>;
}
