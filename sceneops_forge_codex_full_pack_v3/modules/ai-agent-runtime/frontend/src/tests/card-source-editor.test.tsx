import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { expect, test, vi } from 'vitest';
import { CardSourceEditor } from '../CardSourceEditor';
import { agentTasks, type AgentTask } from '../client';

Object.assign(globalThis, {IS_REACT_ACT_ENVIRONMENT:true});
HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open',''); };
HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };

test('card source panel retains drafts and prepares a typed file-scoped edit', async () => {
  const path = 'src/game/systems/inputSystem.ts';
  const prepared = {id:'task-scoped', status:'awaiting_authorization',
    authorization_card:{id:'scope-card',scope:'只允许修改 '+path,cost_notice:'本次最多 8 次模型请求'}} as AgentTask;
  vi.spyOn(agentTasks,'sourceIndex').mockResolvedValue({project_id:'p',card_id:'input',branch:'codex/input',
    architecture:'ECS',truncated:false,files:[{path,section:'src/game/systems',size_bytes:12,editable:true}]});
  vi.spyOn(agentTasks,'sourceFile').mockResolvedValue({path,content:'export const speed = 5;'});
  const prepare = vi.spyOn(agentTasks,'prepare').mockResolvedValue(prepared);
  const authorize = vi.spyOn(agentTasks,'authorize').mockResolvedValue({...prepared,status:'queued'});
  const save = vi.spyOn(agentTasks,'saveSource').mockRejectedValue(new Error('文件已被其他修改更新'));
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  const cache = new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  const click = async (text: string) => {
    const button = [...document.body.querySelectorAll('button')].find(item => item.textContent?.includes(text) || item.getAttribute('aria-label') === text);
    expect(button).toBeTruthy(); await act(async () => button!.click());
  };
  const settle = async () => {await act(async () => {await new Promise(resolve => setTimeout(resolve,30));});};
  const type = async (label: string, value: string) => {
    const area = document.body.querySelector<HTMLTextAreaElement>(`textarea[aria-label="${label}"]`)!;
    expect(area).toBeTruthy();
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value')!.set!.call(area,value);
      area.dispatchEvent(new Event('input',{bubbles:true}));
    });
  };
  try {
    await act(async () => root.render(<QueryClientProvider client={cache}><CardSourceEditor projectId="p" cardId="input" /></QueryClientProvider>));
    await click('架构与源码'); await settle();
    await click('inputSystem.ts'); await settle();
    await type('源码 '+path,'export const speed = 4;');
    await click('返回对话'); await click('架构与源码');
    expect(document.body.querySelector<HTMLTextAreaElement>(`textarea[aria-label="源码 ${path}"]`)!.value).toContain('4');
    await click('保存文件'); await settle();
    expect(save).toHaveBeenCalledWith('p','input',{path,expected_content:'export const speed = 5;',content:'export const speed = 4;',allow_game_execution:false});
    expect(document.body.textContent).toContain('文件已被其他修改更新');
    expect(document.body.querySelector<HTMLTextAreaElement>(`textarea[aria-label="源码 ${path}"]`)!.value).toContain('4');
    await click('放弃本次编辑');
    await act(async () => document.body.querySelector<HTMLInputElement>(`input[aria-label="允许修改 ${path}"]`)!.click());
    await type('局部精修要求','把速度调慢');
    await click('准备局部修改'); await settle();
    expect(prepare).toHaveBeenCalledWith(expect.objectContaining({source_write_paths:[path],execution_mode:'typed-tools',card_id:'input'}));
    expect(authorize).not.toHaveBeenCalled();
    await click('确认范围并开始精修'); await settle();
    expect(authorize).toHaveBeenCalledWith('task-scoped',{authorization_card_id:'scope-card',accept_unknown_cost:true,accept_full_access:false});
  } finally {
    await act(async () => root.unmount());cache.clear();host.remove();vi.restoreAllMocks();
  }
});
