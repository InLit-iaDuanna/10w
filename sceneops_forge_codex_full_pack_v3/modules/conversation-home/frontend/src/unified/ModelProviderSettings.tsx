import { useEffect, useId, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  aiKeys,
  checkProvider,
  readProviderModels,
  saveSettings,
  type AIConnectionRequest,
  type AISettings,
  type AISettingsUpdate,
} from './aiClient.ts';

type Provider = NonNullable<AISettings['provider']>;
type ApiProtocol = NonNullable<AISettings['api_protocol']>;
type AlignmentDetail = NonNullable<AISettings['alignment_detail']>;
type ProviderSettings = AISettings;
type ProviderUpdate = AISettingsUpdate;
type ActionState = { tone: 'success' | 'info' | 'error'; message: string } | null;

/** A write-only provider configuration surface. Secret input is never sent to TanStack MutationCache. */
export function ModelProviderSettings({ settings, disabled = false, compact = false }: { settings: AISettings; disabled?: boolean; compact?: boolean }) {
  const cache = useQueryClient();
  const current: ProviderSettings = settings;
  const [open, setOpen] = useState(false);
  const [provider, setProvider] = useState<Provider>((current.provider as Provider | undefined) ?? 'codebuddycli');
  const [model, setModel] = useState(current.model);
  const [providerChanged, setProviderChanged] = useState(false);
  const [modelChanged, setModelChanged] = useState(false);
  const [baseUrl, setBaseUrl] = useState(current.base_url ?? '');
  const [apiKey, setApiKey] = useState('');
  const [apiProtocol, setApiProtocol] = useState<ApiProtocol>(current.api_protocol ?? 'chat-completions');
  const [streaming, setStreaming] = useState(current.streaming ?? true);
  const [alignmentDetail, setAlignmentDetail] = useState<AlignmentDetail>(current.alignment_detail ?? 'standard');
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([]);
  const [action, setAction] = useState<'models' | 'connection' | null>(null);
  const [actionState, setActionState] = useState<ActionState>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  const actionController = useRef<AbortController | null>(null);
  const modelListId = useId();
  useEffect(() => () => actionController.current?.abort(), []);
  useEffect(() => {if(open && dialog.current && !dialog.current.open) dialog.current.showModal();},[open]);
  useEffect(() => {
    if (!open) return;
    setProvider((current.provider as Provider | undefined) ?? 'codebuddycli');
    setModel(current.model);
    setProviderChanged(false);
    setModelChanged(false);
    setBaseUrl(current.base_url ?? '');
    setApiKey('');
    setApiProtocol(current.api_protocol ?? 'chat-completions');
    setStreaming(current.streaming ?? true);
    setAlignmentDetail(current.alignment_detail ?? 'standard');
    setDiscoveredModels([]);
    setAction(null);
    setActionState(null);
    setError('');
  }, [open, current.provider, current.model, current.base_url, current.api_protocol, current.streaming, current.alignment_detail]);
  const compatible = provider === 'openai-compatible';
  const endpointChanged = compatible && baseUrl.trim() !== (current.base_url ?? '').trim();
  const valid = !!model.trim() && (!compatible || !!baseUrl.trim());
  const keyAvailable = !compatible || !!apiKey || (!endpointChanged && current.api_key_configured);
  const canProbe = (!compatible || (!!baseUrl.trim() && keyAvailable)) && !saving && !action;
  const busy = saving || action !== null;
  function clearActionState() {
    setActionState(null);
    setDiscoveredModels([]);
  }
  function changeProvider(nextProvider: Provider) {
    setProvider(nextProvider);
    setProviderChanged(nextProvider !== current.provider);
    setModel(nextProvider === current.provider ? current.model : nextProvider === 'openai-compatible' ? '' : 'cli-default');
    setModelChanged(false);
    setApiKey('');
    clearActionState();
    setError('');
  }
  function probeFields() {
    return {
      provider,
      ...(compatible ? { base_url: baseUrl.trim(), ...(apiKey ? { api_key: apiKey } : {}) } : {}),
    };
  }
  async function loadModels() {
    if (!canProbe) return;
    actionController.current?.abort();
    const controller = new AbortController();
    actionController.current = controller;
    setAction('models'); setActionState({ tone: 'info', message: '正在获取模型列表…' }); setError('');
    try {
      const result = await readProviderModels(probeFields(), controller.signal);
      const values = result.models.map(item => item.id);
      setDiscoveredModels(values);
      if (provider === current.provider && (!compatible || sameEndpoint(baseUrl, current.base_url))) {
        await cache.invalidateQueries({ queryKey: aiKeys.models });
      }
      setActionState({ tone: result.mode === 'live' ? 'success' : 'info', message: result.message });
    } catch (cause) {
      if (!controller.signal.aborted) setActionState({ tone: 'error',
        message: cause instanceof Error ? cause.message : String(cause) });
    } finally {
      if (actionController.current === controller) {
        actionController.current = null;
        setAction(null);
      }
    }
  }
  async function testConnection() {
    if (!canProbe || !valid) return;
    actionController.current?.abort();
    const controller = new AbortController();
    actionController.current = controller;
    const body: AIConnectionRequest = {
      ...probeFields(), model: model.trim(),
      api_protocol: compatible ? apiProtocol : 'chat-completions', streaming,
    };
    setAction('connection'); setActionState({ tone: 'info', message: '正在发送最小连接测试…' }); setError('');
    try {
      const result = await checkProvider(body, controller.signal);
      setActionState({ tone: 'success', message: `${result.message} ${result.latency_ms} ms` });
    } catch (cause) {
      if (!controller.signal.aborted) setActionState({ tone: 'error',
        message: cause instanceof Error ? cause.message : String(cause) });
    } finally {
      if (actionController.current === controller) {
        actionController.current = null;
        setAction(null);
      }
    }
  }
  async function submit() {
    if (!valid || saving || action) return;
    // A provider-only update deliberately lets the server recall that provider's remembered model.
    const next: ProviderUpdate = { provider } as ProviderUpdate;
    if (!providerChanged || modelChanged || compatible) next.model = model.trim();
    if (compatible) next.base_url = baseUrl.trim();
    if (compatible) next.api_protocol = apiProtocol;
    next.streaming = streaming;
    next.alignment_detail = alignmentDetail;
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
  function closeDialog() {
    actionController.current?.abort();
    actionController.current = null;
    setApiKey('');
    setOpen(false);
  }
  return <>
    <button className={`unified-ai-provider-button${compact ? ' is-icon' : ''}`} aria-label="模型与提供方设置" title="模型与提供方设置" type="button" disabled={disabled} onClick={() => setOpen(true)}><svg aria-hidden="true" viewBox="0 0 16 16"><path d="M8 2.2a1.4 1.4 0 0 1 1.3.9l.2.5c.3.1.6.3.9.5l.6-.1a1.4 1.4 0 0 1 1.5.7l.5.8a1.4 1.4 0 0 1-.2 1.6l-.4.4v1l.4.4a1.4 1.4 0 0 1 .2 1.6l-.5.8a1.4 1.4 0 0 1-1.5.7l-.6-.1-.9.5-.2.5a1.4 1.4 0 0 1-1.3.9h-1a1.4 1.4 0 0 1-1.3-.9l-.2-.5-.9-.5-.6.1a1.4 1.4 0 0 1-1.5-.7l-.5-.8a1.4 1.4 0 0 1 .2-1.6l.4-.4v-1l-.4-.4A1.4 1.4 0 0 1 2 5.5l.5-.8A1.4 1.4 0 0 1 4 4l.6.1.9-.5.2-.5A1.4 1.4 0 0 1 7 2.2h1Z"/><circle cx="7.5" cy="8" r="1.8"/></svg>{!compact && '提供方'}</button>
    {open && <dialog ref={dialog} className="unified-ai-provider-dialog" aria-label="AI 提供方设置"
      onCancel={event => { event.preventDefault(); if (!saving) closeDialog(); }}>
      <header>
        <div><span className="tool-kicker">AI 连接</span><h2>模型与提供方</h2>
          <p>保存后用于对话；只有点击“获取模型”或“检查连接”时，才会探测当前填写的服务。</p></div>
        <button type="button" aria-label="关闭设置" disabled={saving} onClick={closeDialog}>
          <svg aria-hidden="true" viewBox="0 0 16 16"><path d="m4 4 8 8M12 4l-8 8"/></svg>
        </button>
      </header>
      <div className="unified-ai-provider-note"><i aria-hidden="true" /><span>当前配置</span>
        <strong>{providerLabel(String(current.provider))}</strong>
        <small>{current.model} · {alignmentLabel(current.alignment_detail)}对齐 · {current.streaming !== false ? '流式' : '非流式'}{current.provider === 'openai-compatible' ? ` · ${protocolLabel(current.api_protocol)}` : ''}</small>
      </div>
      <div className="unified-ai-provider-fields">
        <label><span>提供方</span><select value={provider} disabled={busy}
          onChange={event => changeProvider(event.target.value as Provider)}>
          <option value="codebuddycli">CodeBuddy CLI</option>
          <option value="codexcli">Codex CLI</option>
          <option value="openai-compatible">OpenAI 兼容服务</option>
        </select></label>
        <label><span>模型 {compatible && <em>必填</em>}</span>
          <input list={modelListId} value={model} disabled={busy}
            placeholder={compatible ? '输入或获取兼容服务模型' : provider === 'codexcli' ? '输入 Codex 模型 ID，或保留 cli-default' : 'cli-default'}
            onChange={event => { setModel(event.target.value); setModelChanged(true); setActionState(null); }} />
          <datalist id={modelListId}>{discoveredModels.map(item => <option key={item} value={item} />)}</datalist>
        </label>
      </div>
      <fieldset className="unified-ai-alignment" disabled={busy}>
        <legend><span>对齐详细程度</span><small>控制项目策划与建模需求的追问数量</small></legend>
        <div role="radiogroup" aria-label="对齐详细程度">{ALIGNMENT_OPTIONS.map(option => <button
          type="button" role="radio" key={option.value} aria-checked={alignmentDetail === option.value}
          data-selected={alignmentDetail === option.value} onClick={() => setAlignmentDetail(option.value)}>
          <span><strong>{option.label}</strong><small>{option.questions}</small></span>
          <small>{option.description}</small>
        </button>)}</div>
      </fieldset>
      <div className="unified-ai-provider-options">
        <label className="unified-ai-provider-check"><input type="checkbox" checked={streaming}
          disabled={busy} onChange={event => { setStreaming(event.target.checked); setActionState(null); }} />
          <span>流式输出</span><small>开启后逐段显示真实模型增量；关闭后等待完整回复。</small>
        </label>
      </div>
      {compatible && <div className="unified-ai-provider-fields unified-ai-provider-advanced">
        <div className="unified-ai-provider-section-title"><span>兼容服务连接</span><small>密钥与完整服务地址绑定</small></div>
        <label><span>服务地址 <em>必填</em></span><input type="url" value={baseUrl} disabled={busy}
          placeholder="https://provider.example/v1"
          onChange={event => { setBaseUrl(event.target.value); clearActionState(); }} />
          <small>填写 API 根地址，例如以 /v1 结尾；不会跟随重定向。</small></label>
        <label><span>API Key <em>只写 · 可选</em></span><input type="password" value={apiKey}
          autoComplete="new-password" disabled={busy}
          placeholder={endpointChanged ? '新地址需填写密钥' : current.api_key_configured ? '当前地址已配置；留空保持不变' : '输入后只写入，不会再次显示'}
          onChange={event => { setApiKey(event.target.value); setActionState(null); }} />
          <small>{endpointChanged ? '新地址不会复用原地址的密钥。' : current.api_key_configured ? '仅输入新值时替换当前地址的密钥。' : '此地址尚未配置密钥，只随保存或主动检查请求发送。'}</small>
        </label>
        <label><span>接口格式</span><select value={apiProtocol} disabled={busy}
          onChange={event => { setApiProtocol(event.target.value as ApiProtocol); setActionState(null); }}>
          <option value="chat-completions">Chat Completions</option>
          <option value="responses">Responses API</option>
        </select><small>请求分别发送到 /chat/completions 或 /responses；失败不自动回退。</small></label>
      </div>}
      <div className="unified-ai-provider-probe">
        <div><button type="button" disabled={!canProbe} onClick={() => void loadModels()}>
          {action === 'models' ? '获取中…' : '获取模型'}</button>
          <button type="button" disabled={!canProbe || !valid} onClick={() => void testConnection()}>
            {action === 'connection' ? '检查中…' : '检查连接'}</button></div>
        <small>连接检查会按当前接口和流式设置发送一次最小模型请求，可能计入服务额度；不会保存未提交配置。</small>
      </div>
      {actionState && <p className="unified-ai-provider-result" data-tone={actionState.tone}
        role={actionState.tone === 'error' ? 'alert' : 'status'}>{actionState.message}</p>}
      {!keyAvailable && compatible && <p role="alert">当前地址没有可用密钥，请先填写 API Key。</p>}
      {error && <p role="alert">保存失败：{error}。当前输入仍保留，可修改后重试。</p>}
      <footer><button type="button" onClick={closeDialog} disabled={saving}>取消</button>
        <button className="unified-ai-save-provider" type="button" onClick={() => void submit()}
          disabled={busy || !valid}>{saving ? '保存中…' : '保存设置'}</button></footer>
    </dialog>}
  </>;
}

function providerLabel(provider: string) {
  return { codebuddycli: 'CodeBuddy CLI', codexcli: 'Codex CLI', 'openai-compatible': 'OpenAI 兼容服务' }[provider] ?? provider;
}

function protocolLabel(protocol: string | undefined) {
  return protocol === 'responses' ? 'Responses API' : 'Chat Completions';
}

const ALIGNMENT_OPTIONS: { value: AlignmentDetail; label: string; questions: string; description: string }[] = [
  { value: 'concise', label: '精简', questions: '最多 2 问', description: '只确认会阻塞制作的核心决定' },
  { value: 'standard', label: '标准', questions: '最多 4 问', description: '覆盖目标、范围、风格与关键约束' },
  { value: 'deep', label: '深入', questions: '最多 8 问', description: '继续确认边界、细节与验收偏好' },
];

function alignmentLabel(detail: string | undefined) {
  return ALIGNMENT_OPTIONS.find(option => option.value === detail)?.label ?? '标准';
}

function sameEndpoint(left: string, right: string | null | undefined) {
  const normalize = (value: string | null | undefined) => (value ?? '').trim().replace(/\/+$/, '');
  return normalize(left) === normalize(right);
}
