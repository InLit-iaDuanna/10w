import { ProviderSettingsIcon } from './ProviderSettingsIcon';
import { EnvironmentSetup } from './EnvironmentSetup';
import './provider-settings.css';
import { useEffect, useId, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@sceneops/api-client';
import {
  aiKeys,
  checkProvider,
  readProviderModels,
  repairLocalApi,
  saveSettings,
  type AIConnectionRequest,
  type AIModels,
  type AISettings,
  type AISettingsUpdate,
} from './aiClient.ts';
import { modelPresentation, REASONING_EFFORT_OPTIONS, type ReasoningEffort } from './ModelBrandMark.tsx';

type Provider = NonNullable<AISettings['provider']>;
type ApiProtocol = NonNullable<AISettings['api_protocol']>;
type AlignmentDetail = NonNullable<AISettings['alignment_detail']>;
type ProviderSettings = AISettings;
type ProviderUpdate = AISettingsUpdate;
type ActionState = { tone: 'success' | 'info' | 'error'; message: string; repairable?: boolean } | null;

/** A write-only provider configuration surface. Secret input is never sent to TanStack MutationCache. */
export function ModelProviderSettings({ settings, disabled = false, compact = false }: { settings: AISettings; disabled?: boolean; compact?: boolean }) {
  const cache = useQueryClient();
  const current: ProviderSettings = settings;
  const [open, setOpen] = useState(false);
  const [section, setSection] = useState<'connection'|'preferences'>('connection');
  const tabId = useId();
  const [provider, setProvider] = useState<Provider>((current.provider as Provider | undefined) ?? 'codebuddycli');
  const [model, setModel] = useState(current.model);
  const [providerChanged, setProviderChanged] = useState(false);
  const [modelChanged, setModelChanged] = useState(false);
  const [baseUrl, setBaseUrl] = useState(current.base_url ?? '');
  const [apiKey, setApiKey] = useState('');
  const [apiProtocol, setApiProtocol] = useState<ApiProtocol>(current.api_protocol ?? 'chat-completions');
  const [streaming, setStreaming] = useState(current.streaming ?? true);
  const [alignmentDetail, setAlignmentDetail] = useState<AlignmentDetail>(current.alignment_detail ?? 'standard');
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningEffort>(current.reasoning_effort ?? 'low');
  const [agentTimeoutMode, setAgentTimeoutMode] = useState<'unlimited' | 'limited'>(current.agent_timeout_minutes == null ? 'unlimited' : 'limited');
  const [agentTimeoutMinutes, setAgentTimeoutMinutes] = useState(String(current.agent_timeout_minutes ?? 60));
  const [selectorEnabled, setSelectorEnabled] = useState(current.selector_provider != null && current.selector_model != null);
  const [selectorProvider, setSelectorProvider] = useState<Provider>((current.selector_provider as Provider | undefined) ?? 'codebuddycli');
  const [selectorModel, setSelectorModel] = useState(current.selector_model ?? 'cli-default');
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([]);
  const [action, setAction] = useState<'models' | 'connection' | 'repair' | null>(null);
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
    const savedProvider = (current.provider as Provider | undefined) ?? 'codebuddycli';
    setSection('connection');
    setProvider(savedProvider);
    setModel(current.model);
    setProviderChanged(false);
    setModelChanged(false);
    setBaseUrl(current.base_url ?? '');
    setApiKey('');
    setApiProtocol(current.api_protocol ?? 'chat-completions');
    setStreaming(current.streaming ?? true);
    setAlignmentDetail(current.alignment_detail ?? 'standard');
    setReasoningEffort(current.reasoning_effort ?? 'low');
    setAgentTimeoutMode(current.agent_timeout_minutes == null ? 'unlimited' : 'limited');
    setAgentTimeoutMinutes(String(current.agent_timeout_minutes ?? 60));
    setSelectorEnabled(current.selector_provider != null && current.selector_model != null);
    setSelectorProvider((current.selector_provider as Provider | undefined) ?? 'codebuddycli');
    setSelectorModel(current.selector_model ?? 'cli-default');
    setDiscoveredModels(cachedModels(cache, savedProvider));
    setAction(null);
    setActionState(null);
    setError('');
  }, [open, current.provider, current.model, current.base_url, current.api_protocol, current.streaming, current.alignment_detail, current.reasoning_effort, current.agent_timeout_minutes, current.selector_provider, current.selector_model]);
  const compatible = provider === 'openai-compatible';
  const endpointChanged = compatible && baseUrl.trim() !== (current.base_url ?? '').trim();
  const parsedAgentTimeout = Number(agentTimeoutMinutes);
  const agentTimeoutValid = agentTimeoutMode === 'unlimited'
    || (Number.isInteger(parsedAgentTimeout) && parsedAgentTimeout >= 1 && parsedAgentTimeout <= 525600);
  const selectorValid = !selectorEnabled || !!selectorModel.trim();
  const valid = !!model.trim() && (!compatible || !!baseUrl.trim()) && agentTimeoutValid && selectorValid;
  const keyAvailable = !compatible || !!apiKey || (!endpointChanged && current.api_key_configured);
  const canProbe = (!compatible || (!!baseUrl.trim() && keyAvailable)) && !saving && !action;
  const busy = saving || action !== null;
  const selectableModels = [...new Set([model, ...discoveredModels].filter(Boolean))];
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
    setActionState(null);
    setDiscoveredModels(cachedModels(cache, nextProvider));
    setError('');
  }
  function probeFields() {
    return {
      provider,
      ...(compatible ? { base_url: baseUrl.trim(), ...(apiKey ? { api_key: apiKey } : {}) } : {}),
    };
  }
  function connectionFields(): AIConnectionRequest {
    return {
      ...probeFields(), model: model.trim(),
      api_protocol: compatible ? apiProtocol : 'chat-completions', streaming,
      reasoning_effort: provider === 'codexcli' ? 'low' : reasoningEffort,
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
    setAction('connection'); setActionState({ tone: 'info', message: '正在发送最小连接测试…' }); setError('');
    try {
      const result = await checkProvider(connectionFields(), controller.signal);
      setActionState({ tone: 'success', message: `${result.message} ${result.latency_ms} ms` });
    } catch (cause) {
      if (!controller.signal.aborted) setActionState({ tone: 'error',
        message: cause instanceof Error ? cause.message : String(cause),
        repairable: cause instanceof ApiError ? cause.status >= 500 : cause instanceof TypeError });
    } finally {
      if (actionController.current === controller) {
        actionController.current = null;
        setAction(null);
      }
    }
  }
  async function repairAndRetryConnection() {
    if (!actionState?.repairable || !valid || busy) return;
    const controller = new AbortController();
    actionController.current = controller;
    setAction('repair'); setActionState({ tone: 'info', message: '正在重启本地服务…' }); setError('');
    try {
      const repaired = await repairLocalApi(controller.signal);
      setActionState({ tone: 'info', message: repaired.message });
      const result = await checkProvider(connectionFields(), controller.signal);
      setActionState({ tone: 'success', message: `${result.message} ${result.latency_ms} ms` });
    } catch (cause) {
      if (!controller.signal.aborted) setActionState({ tone: 'error',
        message: cause instanceof Error ? cause.message : String(cause), repairable: true });
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
    next.reasoning_effort = reasoningEffort;
    next.agent_timeout_minutes = agentTimeoutMode === 'unlimited' ? null : parsedAgentTimeout;
    next.selector_provider = selectorEnabled ? selectorProvider : null;
    next.selector_model = selectorEnabled ? selectorModel.trim() : null;
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
    {open && <dialog ref={dialog} className="unified-ai-provider-dialog provider-settings-v2" aria-label="AI 提供方设置"
      onCancel={event => { event.preventDefault(); if (!saving) closeDialog(); }}>
      <header>
        <div className="provider-settings-title"><span className="provider-settings-mark"><ProviderSettingsIcon kind="preferences" /></span><div><h2>AI 设置</h2><p>选择模型，调整对话与执行偏好</p></div></div>
        <button type="button" aria-label="关闭设置" disabled={saving} onClick={closeDialog}>
          <svg aria-hidden="true" viewBox="0 0 16 16"><path d="m4 4 8 8M12 4l-8 8"/></svg>
        </button>
      </header>
      <div className="provider-settings-current"><span>正在使用</span><strong>{providerLabel(String(current.provider))}</strong><span>·</span><span>{modelPresentation(current.model, current.provider, current.model).label}</span></div>
      <div className="provider-settings-tabs" role="tablist" aria-label="设置分类">{([
        ['connection','连接与模型'],['preferences','对话与执行'],
      ] as const).map(([value,label]) => <button key={value} type="button" role="tab" id={`${tabId}-${value}`} aria-selected={section===value} aria-controls={`${tabId}-${value}-panel`} tabIndex={section===value?0:-1}
        onClick={() => setSection(value)} onKeyDown={event => {
          if (['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) {event.preventDefault();const next=event.key==='Home'?'connection':event.key==='End'?'preferences':section==='connection'?'preferences':'connection';setSection(next);document.getElementById(`${tabId}-${next}`)?.focus();}
        }}><ProviderSettingsIcon kind={value} />{label}</button>)}</div>
      <div className="provider-settings-body">
      <section role="tabpanel" id={`${tabId}-connection-panel`} aria-labelledby={`${tabId}-connection`} hidden={section!=='connection'}>
      <div className="provider-settings-section-heading"><h3>连接配置</h3><p>保存后应用到后续对话与任务。</p></div>
      <div className="provider-settings-setup"><span>首次使用？先安装工具并登录账号。</span><EnvironmentSetup /></div>
      <div className="unified-ai-provider-fields">
        <label><span>提供方</span><select value={provider} disabled={busy}
          onChange={event => changeProvider(event.target.value as Provider)}>
          <option value="codebuddycli">CodeBuddy CLI</option>
          <option value="codexcli">Codex CLI</option>
          <option value="openai-compatible">OpenAI 兼容服务</option>
        </select></label>
        <label><span>模型 {compatible && <em>必填</em>}</span>
          {provider === 'codexcli' ? <select aria-label="Codex 模型" value={model} disabled={busy}
            onChange={event => { setModel(event.target.value); setModelChanged(true); setActionState(null); }}>
            {selectableModels.map(item => <option key={item} value={item}>{item === 'cli-default' ? 'CLI 默认模型' : item}</option>)}
          </select> : <input list={modelListId} value={model} disabled={busy}
            placeholder={compatible ? '输入或获取兼容服务模型' : 'cli-default'}
            onChange={event => { setModel(event.target.value); setModelChanged(true); setActionState(null); }} />}
          <datalist id={modelListId}>{discoveredModels.map(item => <option key={item} value={item} />)}</datalist>
          {provider === 'codexcli' && discoveredModels.length <= 1 && <small>点击“获取模型”读取当前 Codex 账号的可选模型。</small>}
        </label>
        {provider !== 'codexcli' && <label><span>思考强度</span><select value={reasoningEffort} disabled={busy}
          onChange={event => { setReasoningEffort(event.target.value as ReasoningEffort); setActionState(null); }}>
          {REASONING_EFFORT_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select><small>{compatible ? '按所选接口发送标准推理参数；模型不支持时会直接报错。' : '控制模型推理投入，默认使用低强度。'}</small></label>}
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
          <ProviderSettingsIcon kind="models" />{action === 'models' ? '获取中…' : '获取模型'}</button>
          <button type="button" disabled={!canProbe || !valid} onClick={() => void testConnection()}>
            <ProviderSettingsIcon kind="connection" />{action === 'connection' ? '检查中…' : '检查连接'}</button></div>
        <small>仅主动检查时发送测试请求，可能计费；不会自动保存配置。</small>
      </div>
      </section>
      <section role="tabpanel" id={`${tabId}-preferences-panel`} aria-labelledby={`${tabId}-preferences`} hidden={section!=='preferences'}>
      <div className="provider-settings-section-heading"><h3>对话与执行</h3><p>控制追问深度、回复方式和任务时长。</p></div>
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
      <fieldset className="unified-ai-agent-timeout" disabled={busy}>
        <legend><span>Agent 单次执行时限</span><small>新任务使用此设置；默认无限制</small></legend>
        <div role="radiogroup" aria-label="Agent 单次执行时限">
          <button type="button" role="radio" aria-checked={agentTimeoutMode === 'unlimited'}
            data-selected={agentTimeoutMode === 'unlimited'}
            onClick={() => { setAgentTimeoutMode('unlimited'); setActionState(null); }}>
            <strong>无限制</strong><small>持续运行，直到完成、报错或你点击取消</small>
          </button>
          <button type="button" role="radio" aria-checked={agentTimeoutMode === 'limited'}
            data-selected={agentTimeoutMode === 'limited'}
            onClick={() => { setAgentTimeoutMode('limited'); setActionState(null); }}>
            <strong>自定义</strong><small>按分钟限制本次 Agent 运行</small>
          </button>
        </div>
        {agentTimeoutMode === 'limited' && <label><span>分钟</span><input type="number" min="1" max="525600" step="1"
          value={agentTimeoutMinutes} onChange={event => { setAgentTimeoutMinutes(event.target.value); setActionState(null); }} />
          <small>范围 1–525600 分钟；仅影响保存后新建的任务。</small></label>}
      </fieldset>
      <fieldset className="unified-ai-agent-timeout" disabled={busy}>
        <legend><span>制作推荐模型</span><small>在专业制作开始前挑选本次资产、经验与制作方式</small></legend>
        <label className="unified-ai-provider-check"><input type="checkbox" checked={selectorEnabled}
          onChange={event => { setSelectorEnabled(event.target.checked); setActionState(null); }} />
          <span>启用独立推荐模型</span><small>每个制作请求最多调用一次；失败后主制作仍会继续。</small>
        </label>
        {selectorEnabled && <div className="unified-ai-provider-fields">
          <label><span>推荐服务</span><select value={selectorProvider}
            onChange={event => { const next = event.target.value as Provider; setSelectorProvider(next);
              setSelectorModel(next === 'openai-compatible' ? '' : 'cli-default'); setActionState(null); }}>
            <option value="codebuddycli">CodeBuddy CLI</option>
            <option value="codexcli">Codex CLI</option>
            <option value="openai-compatible">OpenAI 兼容服务</option>
          </select></label>
          <label><span>推荐模型 <em>必填</em></span><input value={selectorModel}
            list={`${modelListId}-selector`} placeholder="输入推荐模型"
            onChange={event => { setSelectorModel(event.target.value); setActionState(null); }} />
            <datalist id={`${modelListId}-selector`}>{cachedModels(cache, selectorProvider).map(item => <option key={item} value={item} />)}</datalist>
            <small>复用该服务已保存的连接与凭据，不改变上方主模型。</small>
          </label>
        </div>}
      </fieldset>
      {!agentTimeoutValid && <p role="alert">请输入 1 到 525600 之间的整数分钟数。</p>}
      {!selectorValid && <p role="alert">请填写制作推荐模型。</p>}
      </section>
      {actionState && <div className="unified-ai-provider-result" data-tone={actionState.tone}
        role={actionState.tone === 'error' ? 'alert' : 'status'}><span>{actionState.message}</span>
        {actionState.tone === 'error' && actionState.repairable && <button type="button"
          onClick={() => void repairAndRetryConnection()} disabled={busy}>
          {action === 'repair' ? '正在修复…' : '修复并重新检查'}</button>}</div>}
      {!keyAvailable && compatible && <p role="alert">当前地址没有可用密钥，请先填写 API Key。</p>}
      {error && <p role="alert">保存失败：{error}。当前输入仍保留，可修改后重试。</p>}
      </div>
      <footer><span className="provider-settings-save-note">{!agentTimeoutValid ? '请在“对话与执行”中填写有效时限' : !selectorValid ? '请填写制作推荐模型' : !model.trim() ? '请填写模型' : compatible && !baseUrl.trim() ? '请填写服务地址' : '保存后生效'}</span><button type="button" onClick={closeDialog} disabled={saving}>取消</button>
        <button className="unified-ai-save-provider" type="button" onClick={() => void submit()}
          disabled={busy || !valid}>{saving ? '保存中…' : '保存设置'}</button></footer>
    </dialog>}
  </>;
}

function providerLabel(provider: string) {
  return { codebuddycli: 'CodeBuddy CLI', codexcli: 'Codex CLI', 'openai-compatible': 'OpenAI 兼容服务' }[provider] ?? provider;
}

function cachedModels(cache: ReturnType<typeof useQueryClient>, provider: Provider) {
  return cache.getQueryData<AIModels>(aiKeys.models)?.models
    .filter(item => item.provider === provider).map(item => item.id) ?? [];
}


const ALIGNMENT_OPTIONS: { value: AlignmentDetail; label: string; questions: string; description: string }[] = [
  { value: 'concise', label: '精简', questions: '最多 2 问', description: '只确认会阻塞制作的核心决定' },
  { value: 'standard', label: '标准', questions: '最多 4 问', description: '覆盖目标、范围、风格与关键约束' },
  { value: 'deep', label: '深入', questions: '最多 8 问', description: '继续确认边界、细节与验收偏好' },
];



function sameEndpoint(left: string, right: string | null | undefined) {
  const normalize = (value: string | null | undefined) => (value ?? '').trim().replace(/\/+$/, '');
  return normalize(left) === normalize(right);
}
