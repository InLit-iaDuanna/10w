import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {expect, test, vi} from 'vitest';
import {workspaceClient} from '@sceneops/workspace-client';
import {WorkspaceProjects} from '../WorkspaceProjects';

Object.assign(globalThis, {IS_REACT_ACT_ENVIRONMENT: true});
HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };

// Deterministic folder fixture; these tests never write to the local filesystem.
const folders = {path:'/fixture', parent_path:null, entries:[]};
async function mount() {
  const cache = new QueryClient({defaultOptions:{queries:{retry:false, staleTime:Infinity}}});
  cache.setQueryData(['workspace-projects'], {projects:[]});
  cache.setQueryData(['workspace-folder-projects'], {projects:[]});
  cache.setQueryData(['workspace-folders','home'], folders);
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host); const onSelect = vi.fn(); const onClose = vi.fn();
  await act(async () => root.render(<QueryClientProvider client={cache}><WorkspaceProjects projectId={null} onSelect={onSelect} onClose={onClose}/></QueryClientProvider>));
  const button = (name:string) => [...host.querySelectorAll('button')].find(item => item.textContent === name)!;
  const click = async (name:string) => { await act(async () => button(name).click()); };
  return {host, cache, button, click, onSelect, onClose, async cleanup() {await act(async () => root.unmount()); host.remove(); cache.clear(); vi.restoreAllMocks();}};
}

test('project modal focuses the name and Escape returns through the views', async () => {
  const ui = await mount();
  try {
    expect(ui.host.querySelector('dialog[open]')).not.toBeNull();
    await ui.click('新建项目');
    expect(document.activeElement).toBe(ui.host.querySelector('input'));
    expect(ui.button('创建项目').disabled).toBe(true);
    await act(async () => ui.host.querySelector('dialog')!.dispatchEvent(new Event('cancel',{cancelable:true})));
    expect(ui.host.textContent).toContain('你的项目');
    expect(ui.onClose).not.toHaveBeenCalled();
    await act(async () => ui.host.querySelector('dialog')!.dispatchEvent(new Event('cancel',{cancelable:true})));
    expect(ui.onClose).toHaveBeenCalledOnce();
  } finally {await ui.cleanup();}
});

test('removal presents both choices and permanent deletion requires the exact path', async () => {
  const ui = await mount();
  const remove = vi.spyOn(workspaceClient, 'forgetFolderProject').mockResolvedValue();
  const destroy = vi.spyOn(workspaceClient, 'deleteFolderProjectFiles').mockRejectedValue(new Error('目录身份不匹配'));
  const project = {project_id:'fixture', name:'fixture', root_path:'/fixture/game', root_available:true, project_kind:'sceneops_created'};
  try {
    await act(async () => {ui.cache.setQueryData(['workspace-folder-projects'], {projects:[project]});});
    await act(async () => new Promise(resolve => setTimeout(resolve, 0)));
    await act(async () => ui.host.querySelector<HTMLButtonElement>('[aria-label="删除或移除 fixture"]')!.click());
    expect(remove).not.toHaveBeenCalled();
    expect(destroy).not.toHaveBeenCalled();
    expect(ui.button('确认移除').disabled).toBe(false);
    await act(async () => ui.host.querySelectorAll<HTMLInputElement>('input[type=radio]')[1].click());
    expect(ui.button('永久删除本地文件').disabled).toBe(true);
    const input = ui.host.querySelector<HTMLInputElement>('input[autocomplete=off]')!;
    await act(async () => {Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input, project.root_path); input.dispatchEvent(new Event('input',{bubbles:true}));});
    await ui.click('永久删除本地文件');
    expect(destroy).toHaveBeenCalledWith('fixture', {confirmed_root_path:project.root_path, confirm_permanent_delete:true});
    expect(ui.host.querySelector('[role=alert]')?.textContent).toBe('目录身份不匹配');
    expect(remove).not.toHaveBeenCalled();
  } finally {await ui.cleanup();}
});

test('creation failure stays in the modal with a visible error', async () => {
  const create = vi.spyOn(workspaceClient,'createFolderProject').mockRejectedValue(new Error('目录不可写'));
  const ui = await mount();
  try {
    await ui.click('新建项目');
    const name = ui.host.querySelector('input')!;
    await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(name,'fixture-game'); name.dispatchEvent(new Event('input',{bubbles:true})); });
    await act(async () => ui.host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
    expect(create).toHaveBeenCalledOnce();
    expect(ui.host.querySelector('[role=alert]')?.textContent).toBe('目录不可写');
    expect(ui.host.querySelector('dialog')?.getAttribute('aria-label')).toBe('新建项目');
    expect(ui.onSelect).not.toHaveBeenCalled();
  } finally {await ui.cleanup();}
});
