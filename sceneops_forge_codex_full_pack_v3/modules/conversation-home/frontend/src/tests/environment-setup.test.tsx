import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { test, expect, vi } from 'vitest';
import { EnvironmentSetup } from '../unified/EnvironmentSetup';
import * as setupApi from '../unified/setupClient';
import * as aiApi from '../unified/aiClient';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };

const missing: setupApi.CLISetupStatus = {
  platform: 'darwin', install_supported: true, terminal_supported: true, npm_available: true,
  tools: [{ provider: 'codebuddycli', label: 'CodeBuddy CLI', installed: false, compatible: false, version: null,
    install_package: '@tencent-ai/codebuddy-code@2.146.0', login_command: 'codebuddy',
    docs_url: 'https://www.codebuddy.cn/docs/cli/quickstart' }],
  operation: { state: 'idle', message: '', provider: null },
};

test('onboarding installs explicitly, verifies login, recovers failure and saves verified provider', async () => {
  localStorage.removeItem('sceneops.environment-setup');
  const current = { provider: 'codexcli', model: 'existing-model', streaming: true, reasoning_effort: 'low',
    api_key_configured: false } as aiApi.AISettings;
  let status = structuredClone(missing);
  vi.spyOn(setupApi, 'readSetup').mockImplementation(async () => status);
  vi.spyOn(aiApi, 'readSettings').mockResolvedValue(current);
  const install = vi.spyOn(setupApi, 'installTools').mockImplementation(async () => {
    status = { ...missing, tools: missing.tools.map(tool => ({ ...tool, installed: true, compatible: true, version: '2.146.0' })),
      operation: { state: 'succeeded', message: 'CLI 已准备好', provider: null } };
    return status;
  });
  const login = vi.spyOn(setupApi, 'loginTool').mockResolvedValue({ message: '已打开终端，请完成登录' });
  const check = vi.spyOn(aiApi, 'checkProvider').mockRejectedValueOnce(new Error('登录未完成'))
    .mockResolvedValueOnce({ message: '连接成功', latency_ms: 12, mode: 'live', provider: 'codebuddycli',
      model: 'cli-default', api_protocol: 'chat-completions', streaming: true, connected: true });
  const save = vi.spyOn(aiApi, 'saveSettings').mockResolvedValue({ ...current, provider: 'codebuddycli', model: 'cli-default' });
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const render = () => root.render(<QueryClientProvider client={cache}><EnvironmentSetup autoOpen /></QueryClientProvider>);
  const button = (name: string) => [...host.querySelectorAll('button')].find(item => item.textContent === name)!;
  const click = async (name: string) => { expect(button(name)).toBeTruthy(); await act(async () => button(name).click()); };
  try {
    await act(async () => render());
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
    expect(host.querySelector('dialog')).toBeTruthy();
    expect(install).not.toHaveBeenCalled(); expect(login).not.toHaveBeenCalled(); expect(check).not.toHaveBeenCalled();
    await click('继续');
    expect(button('下一步：登录').disabled).toBe(true);
    await click('一键安装所选工具');
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
    expect(install).toHaveBeenCalledWith(['codebuddycli'], expect.anything());
    await click('下一步：登录');
    await click('打开终端登录');
    expect(button('完成配置，开始使用').disabled).toBe(true);
    await click('我已登录，检查连接');
    expect(host.textContent).toContain('登录未完成'); expect(save).not.toHaveBeenCalled();
    await click('我已登录，检查连接');
    expect(check).toHaveBeenLastCalledWith(expect.objectContaining({ provider: 'codebuddycli', model: 'cli-default' }), expect.any(AbortSignal));
    expect(button('完成配置，开始使用').disabled).toBe(false);
    await click('完成配置，开始使用');
    expect(save).toHaveBeenCalledWith({ provider: 'codebuddycli', model: 'cli-default' }, expect.anything());
    expect(host.querySelector('dialog')).toBeNull();
    expect(localStorage.getItem('sceneops.environment-setup')).toBe('completed');
    await click('环境配置');
    expect(host.querySelector('dialog')).toBeTruthy();
  } finally {
    await act(async () => root.unmount()); host.remove(); cache.clear(); vi.restoreAllMocks();
    localStorage.removeItem('sceneops.environment-setup');
  }
});

test('background installation does not block another ready tool or hide progress', async () => {
  localStorage.removeItem('sceneops.environment-setup');
  const status: setupApi.CLISetupStatus = { ...missing,
    tools: missing.tools.map(tool => ({ ...tool, installed: true, compatible: true })),
    operation: { state: 'installing', provider: 'codexcli', message: '正在安装 Codex CLI…' },
  };
  vi.spyOn(setupApi, 'readSetup').mockResolvedValue(status);
  vi.spyOn(aiApi, 'readSettings').mockResolvedValue({ provider: 'codebuddycli', model: 'cli-default' } as aiApi.AISettings);
  const install = vi.spyOn(setupApi, 'installTools');
  const login = vi.spyOn(setupApi, 'loginTool');
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  const cache = new QueryClient();
  const button = (name: string) => [...host.querySelectorAll('button')].find(item => item.textContent === name)!;
  try {
    await act(async () => root.render(<QueryClientProvider client={cache}><EnvironmentSetup autoOpen /></QueryClientProvider>));
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
    expect(host.textContent).toContain('后台安装：正在安装 Codex CLI');
    expect(button('继续').disabled).toBe(false);
    await act(async () => button('继续').click());
    expect(button('下一步：登录').disabled).toBe(false);
    await act(async () => button('下一步：登录').click());
    expect(button('打开终端登录').disabled).toBe(false);
    expect(button('我已登录，检查连接').disabled).toBe(false);
    expect(install).not.toHaveBeenCalled(); expect(login).not.toHaveBeenCalled();
    await act(async () => cache.setQueryData(setupApi.setupKey, { ...status,
      operation: { ...status.operation, provider: 'codebuddycli' } }));
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
    expect(button('打开终端登录').disabled).toBe(true);
    expect(button('上一步').disabled).toBe(false);
  } finally {
    await act(async () => root.unmount()); host.remove(); cache.clear(); vi.restoreAllMocks();
    localStorage.removeItem('sceneops.environment-setup');
  }
});
