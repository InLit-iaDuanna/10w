import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { expect, test, vi } from 'vitest';
import { ExportWorkbench } from '../export/ExportWorkbench';
import { exportApi, type ExportTask } from '../export/client';

const { fireEvent } = createRequire(resolve('modules/character-animation/frontend/package.json'))('@testing-library/react');

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const fixture: ExportTask = {
  id: 'export-demo', project_id: 'project-demo', source_version: 'commit-demo', mode: 'mock', revision: 1,
  settings: { app_name: '试玩游戏', app_id: 'app.sceneops.demo', orientation: 'landscape', allow_dependency_install: false },
  created_at: '2026-09-08T00:00:00Z', updated_at: '2026-09-08T00:00:00Z',
  messages: [{ id: 'message-one', role: 'assistant', content: '安卓缺少 SDK，请配置后继续。', created_at: '2026-09-08T00:00:00Z' }],
  platforms: [
    { platform: 'android', status: 'failed', verification: 'pending', verification_notes: '', verification_device: '', attempts: [{ id: 'attempt-one', number: 1, cancel_requested: false, status: 'failed', stage: 'environment', logs: [], artifacts: [], error: '缺少 Android SDK', started_at: '2026-09-08T00:00:00Z' }] },
    { platform: 'mac-arm64', status: 'succeeded', verification: 'pending', verification_notes: '', verification_device: '', attempts: [{ id: 'attempt-two', number: 1, cancel_requested: false, status: 'succeeded', stage: 'complete', logs: [], artifacts: [{ id: 'artifact-one', name: '试玩游戏.zip', size: 1024, download_url: '/api/projects/project-demo/exports/export-demo/artifacts/artifact-one' }], started_at: '2026-09-08T00:00:00Z' }] },
  ],
};

test('export page preserves partial success, real failures and retry errors beside durable chat', async () => {
  const refreshed: ExportTask = { ...fixture, id: 'export-refreshed', previous_task_id: fixture.id, source_version: 'saved-new:export-refreshed', revision: 1 };
  vi.spyOn(exportApi, 'list').mockResolvedValue([fixture]);
  vi.spyOn(exportApi, 'get').mockImplementation(async (_projectId, taskId) => taskId === refreshed.id ? refreshed : fixture);
  const refresh = vi.spyOn(exportApi, 'refreshSource').mockResolvedValue(refreshed);
  const retry = vi.spyOn(exportApi, 'platformAction').mockRejectedValue(new Error('工具仍未配置'));
  const consent = vi.spyOn(exportApi, 'consent').mockResolvedValue({ ...fixture, revision: 2, settings: { ...fixture.settings, allow_dependency_install: true } });
  let eventSource: { onerror: (() => void) | null };
  vi.stubGlobal('EventSource', class {
    onerror = null; onopen = null;
    constructor() { eventSource = this; }
    addEventListener() {} close() {}
  });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  const settle = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 40)); });
  try {
    await act(async () => root.render(<QueryClientProvider client={cache}><ExportWorkbench projectId="project-demo" /></QueryClientProvider>));
    await settle(); await settle();
    expect(host.textContent).toContain('缺少 Android SDK');
    expect(host.textContent).toContain('包已生成');
    expect(host.textContent).toContain('待设备验证');
    expect(host.textContent).toContain('安卓缺少 SDK，请配置后继续。');
    expect(host.querySelector('a[download]')?.getAttribute('href')).toContain('/artifacts/artifact-one');
    const permission = host.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    expect(permission.checked).toBe(false);
    await act(async () => permission.click()); await settle();
    expect(consent).toHaveBeenCalledWith('project-demo', 'export-demo', { allow_dependency_install: true });
    expect(permission.checked).toBe(true);
    const button = [...host.querySelectorAll('button')].find(item => item.textContent === '继续导出此平台')!;
    await act(async () => button.click()); await settle();
    expect(retry).toHaveBeenCalledWith('project-demo', 'export-demo', 'android', 'continue');
    expect(host.textContent).toContain('工具仍未配置');
    expect(host.querySelector('a[download]')).toBeTruthy();
    await act(async () => eventSource!.onerror?.());
    expect(host.textContent).toContain('实时连接已断开');
    const refreshButton = [...host.querySelectorAll('button')].find(item => item.textContent === '用当前项目重新导出')!;
    await act(async () => refreshButton.click()); await settle();
    expect(refresh).toHaveBeenCalledWith('project-demo', 'export-demo');
    expect(host.textContent).toContain('saved-new:export-refreshed');
    expect(host.textContent).toContain('安卓缺少 SDK，请配置后继续。');
    const previous = [...host.querySelectorAll('button')].find(item => item.textContent === '查看上一导出任务')!;
    expect(previous).toBeTruthy();
    await act(async () => previous.click()); await settle();
    expect(host.textContent).toContain('commit-demo');
  } finally { await act(async () => root.unmount()); cache.clear(); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); }
});

test('restored native task shows real operations, cancel state and completed errors without losing downloads', async () => {
  const running: ExportTask = { ...fixture, native_runs: [{ id: 'native-one', agent_task_id: 'agent-real', status: 'running', logs: [{ timestamp: fixture.created_at, stage: 'tool', message: '检查 Java 版本' }], started_at: fixture.created_at, cancel_requested: false }] };
  vi.spyOn(exportApi, 'list').mockResolvedValue([running]);
  vi.spyOn(exportApi, 'get').mockResolvedValue(running);
  const cancel = vi.spyOn(exportApi, 'cancelAgent').mockResolvedValue({ ...running, revision: 2, native_runs: [{ ...running.native_runs![0], cancel_requested: true }] });
  vi.stubGlobal('EventSource', class { onerror = null; onopen = null; addEventListener() {} close() {} });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  const settle = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 40)); });
  try {
    await act(async () => root.render(<QueryClientProvider client={cache}><ExportWorkbench projectId="project-demo" /></QueryClientProvider>));
    await settle(); await settle();
    expect(host.textContent).toContain('检查 Java 版本');
    expect(host.textContent).toContain('agent-real');
    expect(host.textContent).toContain('可操作导出目录以外的环境');
    const stop = [...host.querySelectorAll('button')].find(button => button.textContent === '停止 Agent')!;
    await act(async () => stop.click()); await settle();
    expect(cancel).toHaveBeenCalledWith('project-demo', 'export-demo');
    expect(stop.disabled).toBe(true);
    expect(host.textContent).toContain('正在停止 Agent');
    await act(async () => cache.setQueryData(['project-export', 'project-demo', 'export-demo'], { ...running, revision: 3, native_runs: [{ ...running.native_runs![0], status: 'failed', error: '原生提供方尚未连接' }] }));
    await settle();
    expect(host.textContent).toContain('原生提供方尚未连接');
    expect(host.querySelector('a[download]')).toBeTruthy();
    expect([...host.querySelectorAll('button')].some(button => button.textContent === '停止 Agent')).toBe(false);
  } finally { await act(async () => root.unmount()); cache.clear(); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); }
});

test('explicit native submit grants execution while discussion does not', async () => {
  vi.spyOn(exportApi, 'list').mockResolvedValue([fixture]);
  vi.spyOn(exportApi, 'get').mockResolvedValue(fixture);
  const send = vi.spyOn(exportApi, 'message').mockResolvedValue(fixture);
  vi.stubGlobal('EventSource', class { onerror = null; onopen = null; addEventListener() {} close() {} });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  const settle = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 40)); });
  const input = async (content: string) => {
    const textarea = host.querySelector('textarea[aria-label="给导出 Agent 的消息"]')!;
    await act(async () => {
      fireEvent.change(textarea, { target: { value: content } });
    });
  };
  try {
    await act(async () => root.render(<QueryClientProvider client={cache}><ExportWorkbench projectId="project-demo" /></QueryClientProvider>));
    await settle(); await settle();
    await input('补齐工具并继续');
    await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === '发送并执行')!.click());
    await settle();
    expect(send).toHaveBeenLastCalledWith('project-demo', 'export-demo', { content: '补齐工具并继续', execution_mode: 'native', accept_full_access: true });
    await act(async () => {
      const select = host.querySelector<HTMLSelectElement>('select[aria-label="导出 Agent 处理方式"]')!;
      select.value = 'discuss'; select.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await input('解释错误');
    await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === '发送讨论')!.click());
    await settle();
    expect(send).toHaveBeenLastCalledWith('project-demo', 'export-demo', { content: '解释错误', execution_mode: 'discuss', accept_full_access: false });
  } finally { await act(async () => root.unmount()); cache.clear(); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); }
});

test('new export explicitly starts native Agent with displayed computer scope', async () => {
  vi.spyOn(exportApi, 'list').mockResolvedValue([]);
  vi.spyOn(exportApi, 'get').mockResolvedValue(fixture);
  const create = vi.spyOn(exportApi, 'create').mockResolvedValue(fixture);
  vi.stubGlobal('EventSource', class { onerror = null; onopen = null; addEventListener() {} close() {} });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  const settle = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 40)); });
  try {
    await act(async () => root.render(<QueryClientProvider client={cache}><ExportWorkbench projectId="project-demo" projectName="试玩游戏" /></QueryClientProvider>));
    await settle(); await settle();
    expect(host.textContent).toContain('开始即允许 Agent 在当前电脑执行命令');
    expect(create).not.toHaveBeenCalled();
    await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === '让 Agent 开始导出')!.click());
    await settle();
    expect(create).toHaveBeenCalledWith('project-demo', {
      platforms: ['android'], execution_mode: 'native', accept_full_access: true,
      settings: { app_name: '试玩游戏', app_id: '', orientation: 'landscape', allow_dependency_install: false },
    });
  } finally { await act(async () => root.unmount()); cache.clear(); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); }
});
