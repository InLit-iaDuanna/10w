import { useEffect, useId, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiKeys, checkProvider, readSettings, saveSettings } from './aiClient.ts';
import { installTools, loginTool, readSetup, setupKey, type CLIProvider } from './setupClient.ts';
import './environment-setup.css';

const STORAGE_KEY = 'sceneops.environment-setup';
const choices: { provider: CLIProvider; label: string; description: string }[] = [
  { provider: 'codebuddycli', label: 'CodeBuddy CLI', description: '通过 CodeBuddy 账号连接腾讯代码助手' },
  { provider: 'codexcli', label: 'Codex CLI', description: '通过 ChatGPT 账号连接 OpenAI Codex' },
];

export function EnvironmentSetup({ autoOpen = false, onOpenChange }: {
  autoOpen?: boolean; onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen] = useState(() => autoOpen && !localStorage.getItem(STORAGE_KEY));
  useEffect(() => { onOpenChange?.(open); }, [open, onOpenChange]);
  return <>
    <button className="environment-setup-trigger" type="button" onClick={() => setOpen(true)}>环境配置</button>
    {open && <SetupDialog onClose={completed => {
      localStorage.setItem(STORAGE_KEY, completed ? 'completed' : 'dismissed');
      setOpen(false);
    }} />}
  </>;
}

function SetupDialog({ onClose }: { onClose: (completed: boolean) => void }) {
  const cache = useQueryClient();
  const titleId = useId();
  const dialog = useRef<HTMLDialogElement>(null);
  const controller = useRef<AbortController | null>(null);
  const [step, setStep] = useState(0);
  const [selected, setSelected] = useState<CLIProvider[]>(['codebuddycli']);
  const [primary, setPrimary] = useState<CLIProvider>('codebuddycli');
  const [verified, setVerified] = useState<CLIProvider[]>([]);
  const [checking, setChecking] = useState<CLIProvider | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const setup = useQuery({ queryKey: setupKey, queryFn: ({ signal }) => readSetup(signal), retry: false,
    refetchInterval: query => query.state.data?.operation.state === 'installing' ? 1500 : false });
  const settings = useQuery({ queryKey: aiKeys.settings, queryFn: ({ signal }) => readSettings(signal), retry: false });
  const install = useMutation({ mutationFn: installTools, onSuccess: value => {
    cache.setQueryData(setupKey, value);
    void cache.invalidateQueries({ queryKey: aiKeys.models });
  } });
  const login = useMutation({ mutationFn: loginTool, onSuccess: value => setNotice(value.message) });
  const save = useMutation({ mutationFn: saveSettings, onSuccess: value => {
    cache.setQueryData(aiKeys.settings, value);
    void cache.invalidateQueries({ queryKey: aiKeys.models });
    onClose(true);
  } });
  useEffect(() => {
    dialog.current?.showModal();
    return () => controller.current?.abort();
  }, []);
  useEffect(() => {
    if (setup.data?.operation.state === 'succeeded') void cache.invalidateQueries({ queryKey: aiKeys.models });
  }, [setup.data?.operation.state, cache]);

  const installing = install.isPending || setup.data?.operation.state === 'installing';
  const busy = login.isPending || checking !== null || save.isPending;
  const toolInstalling = (provider: CLIProvider) => installing
    && (!setup.data?.operation.provider || setup.data.operation.provider === provider);
  const selectedTools = setup.data?.tools.filter(tool => selected.includes(tool.provider)) ?? [];
  const installed = selectedTools.length === selected.length && selectedTools.every(tool => tool.installed && tool.compatible && !toolInstalling(tool.provider));
  const failure = error || setup.error?.message || settings.error?.message || install.error?.message || login.error?.message || save.error?.message;
  function toggle(provider: CLIProvider) {
    const next = selected.includes(provider) ? selected.filter(item => item !== provider) : [...selected, provider];
    setSelected(next);
    if (!next.includes(primary) && next.length) setPrimary(next[0]);
  }
  async function verify(provider: CLIProvider) {
    if (!settings.data) return;
    const request = new AbortController();
    controller.current = request;
    setChecking(provider); setError(''); setNotice('正在检查账号授权与模型连接…');
    const current = settings.data;
    try {
      const result = await checkProvider({ provider,
        model: current.provider === provider ? current.model : 'cli-default',
        streaming: current.streaming, api_protocol: 'chat-completions',
        reasoning_effort: current.reasoning_effort,
      }, request.signal);
      setVerified(previous => [...new Set([...previous, provider])]);
      setNotice(result.message);
    } catch (cause) {
      if (!request.signal.aborted) {
        setVerified(previous => previous.filter(item => item !== provider));
        setError(cause instanceof Error ? cause.message : String(cause));
      }
    } finally {
      if (!request.signal.aborted) setChecking(null);
    }
  }

  return <dialog className="environment-setup-dialog" ref={dialog} aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); if (!save.isPending) onClose(false); }}>
    <header><span className="environment-setup-eyebrow">开始使用 SCENEOPS</span>
      <h2 id={titleId}>{['先连接你的 AI 助手', '准备本地环境', '登录，开始创作'][step]}</h2>
      <p>{['选择你要使用的工具，已有安装会自动识别。', '一键安装所选工具，完成后继续登录账号。', '在官方流程中完成授权，再回到这里检查连接。'][step]}</p>
    </header>
    <ol className="environment-setup-steps" aria-label="配置进度">
      {['选择工具', '安装环境', '登录与连接'].map((label, index) => <li key={label} aria-current={step === index ? 'step' : undefined}
        data-done={step > index}><span>{step > index ? '✓' : index + 1}</span>{label}</li>)}
    </ol>
    <div className="environment-setup-body">
      {installing && <p role="status">后台安装：{setup.data?.operation.message || '正在准备安装…'}。可以继续配置其他已就绪的工具。</p>}
      {step === 0 && <>
        <div className="environment-setup-choices">{choices.map(choice => <label key={choice.provider} data-selected={selected.includes(choice.provider)}>
          <input type="checkbox" checked={selected.includes(choice.provider)} onChange={() => toggle(choice.provider)} />
          <span><strong>{choice.label}</strong><small>{choice.description}</small></span>
          <em>{setup.isPending ? '检测中' : setup.data?.tools.find(tool => tool.provider === choice.provider)?.compatible ? '已就绪' : setup.data ? '待配置' : '未检测'}</em>
        </label>)}</div>
        <p className="environment-setup-hint">可以只选一个，也可以同时安装。已有兼容服务可跳过，在 AI 设置中填写连接信息。</p>
      </>}
      {step === 1 && <>
        <p className="environment-setup-location">配置位置：运行 SceneOps 本地服务的电脑{setup.data ? ` · ${setup.data.platform}` : ''}</p>
        <div className="environment-setup-tools">{selectedTools.map(tool => <div key={tool.provider}>
          <span><strong>{tool.label}</strong><small>{tool.version ?? (tool.installed ? '已安装，版本未知' : tool.install_package)}</small>
            {tool.installed && !tool.compatible && <small>需要工作台适配版本：{tool.install_package}</small>}</span>
          <span>{tool.compatible ? '✓ 已就绪' : setup.data?.operation.provider === tool.provider && installing ? '正在安装…' : tool.installed ? '需适配版本' : '待安装'}</span>
        </div>)}</div>
        <p className="environment-setup-hint">安装到 SceneOps 的用户目录，无需管理员权限。兼容的已有工具会直接复用；需要适配版本时单独安装，保留原有全局工具与登录信息。</p>
        {!installed && setup.data && <>
          {setup.data.install_supported && setup.data.npm_available ? <button type="button" className="environment-setup-primary" disabled={busy || installing}
            onClick={() => { setError(''); install.mutate(selected); }}>{installing ? '正在配置…' : '一键安装所选工具'}</button>
            : <p className="environment-setup-hint">{!setup.data.npm_available ? <>请先安装 <a href="https://nodejs.org/en/download" target="_blank" rel="noreferrer">Node.js LTS</a>，重新启动 SceneOps，再点击重新检测。</> : '当前系统请按下方官方指南安装，然后重新检测。'}</p>}
          <details><summary>查看手动安装方法</summary>{selectedTools.map(tool => <div className="environment-setup-manual" key={tool.provider}>
            <a href={tool.docs_url} target="_blank" rel="noreferrer">{tool.label} 官方安装指南 ↗</a>
            <code>npm install -g {tool.install_package}</code>
          </div>)}</details>
        </>}
        {setup.data && !installing && setup.data.operation.state !== 'idle' && <p role={setup.data?.operation.state === 'failed' ? 'alert' : 'status'}>{setup.data?.operation.message}</p>}
        <button type="button" disabled={busy || setup.isFetching} onClick={() => void setup.refetch()}>{setup.isFetching ? '检测中…' : '重新检测'}</button>
      </>}
      {step === 2 && <>
        <div className="environment-setup-login">{selectedTools.map(tool => <section key={tool.provider}>
          <div className="environment-setup-tool-title"><strong>{tool.label}</strong><span>{verified.includes(tool.provider) ? '✓ 连接已验证' : '待验证登录与连接'}</span></div>
          <p>{tool.provider === 'codexcli' ? '打开登录后，按提示使用 ChatGPT 账号完成授权。' : '打开终端后，选择登录方式，按提示在浏览器中完成授权。'}</p>
          <div className="environment-setup-actions">
            {setup.data?.terminal_supported && <button type="button" disabled={busy || !tool.compatible || toolInstalling(tool.provider)} onClick={() => {
              setError(''); setVerified(previous => previous.filter(item => item !== tool.provider)); login.mutate(tool.provider);
            }}>打开终端登录</button>}
            <button type="button" disabled={busy || !tool.compatible || toolInstalling(tool.provider) || !settings.data} onClick={() => void verify(tool.provider)}>{checking === tool.provider ? '检查中…' : '我已登录，检查连接'}</button>
          </div>
          <details><summary>{setup.data?.terminal_supported ? '手动登录 / 排查' : '在终端登录'}</summary>
            <p>在这台电脑的终端执行：</p><code>{tool.login_command}</code>
            <a href={tool.docs_url} target="_blank" rel="noreferrer">打开官方指南 ↗</a>
          </details>
        </section>)}</div>
        <p className="environment-setup-hint">检查连接会发送一次最小模型请求，可能消耗账号额度。安装成功或打开登录窗口不代表账号已授权。</p>
        <label className="environment-setup-default">默认使用<select value={primary} disabled={busy} onChange={event => setPrimary(event.target.value as CLIProvider)}>
          {selectedTools.map(tool => <option key={tool.provider} value={tool.provider}>{tool.label}</option>)}
        </select></label>
        {notice && <p role="status">{notice}</p>}
      </>}
      {failure && <p role="alert">{failure} <button type="button" disabled={busy} onClick={() => {
        setError(''); install.reset(); login.reset(); save.reset(); void setup.refetch(); void settings.refetch();
      }}>重新读取</button></p>}
    </div>
    <footer><button type="button" disabled={save.isPending} onClick={() => onClose(false)}>{installing ? '后台安装，稍后继续' : '稍后配置'}</button>
      <div>{step > 0 && <button type="button" disabled={busy} onClick={() => { setStep(step - 1); setNotice(''); }}>上一步</button>}
        {step < 2 ? <button className="environment-setup-primary" type="button" disabled={busy || selected.length === 0 || (step === 1 && !installed)} onClick={() => setStep(step + 1)}>{step === 0 ? '继续' : '下一步：登录'}</button>
          : <button className="environment-setup-primary" type="button" disabled={busy || toolInstalling(primary) || !verified.includes(primary)} onClick={() => save.mutate({ provider: primary,
            model: settings.data?.provider === primary ? settings.data.model : 'cli-default',
          })}>{save.isPending ? '保存中…' : '完成配置，开始使用'}</button>}
      </div>
    </footer>
  </dialog>;
}
