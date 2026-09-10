import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {ApiError} from '@sceneops/api-client';
import {test,expect,vi} from 'vitest';
import {ModelProviderSettings} from '../unified/ModelProviderSettings';
import * as api from '../unified/aiClient';
Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};

test('settings tabs preserve drafts and save only on explicit action',async()=>{
 const settings={provider:'openai-compatible',model:'example-model',base_url:'https://example.invalid/v1',api_key_configured:true,api_protocol:'responses',streaming:true,alignment_detail:'standard',reasoning_effort:'low',agent_timeout_minutes:null,selector_provider:'codexcli',selector_model:'economy-model'} as api.AISettings;
 const save=vi.spyOn(api,'saveSettings').mockResolvedValue(settings);
 const probe=vi.spyOn(api,'checkProvider').mockRejectedValue(new Error('must not probe'));
 const models=vi.spyOn(api,'readProviderModels').mockRejectedValue(new Error('must not probe'));
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);const cache=new QueryClient();
 const click=async(name:string)=>{const button=[...document.querySelectorAll('button')].find(item=>item.getAttribute('aria-label')===name||item.textContent===name)!;expect(button).toBeTruthy();await act(async()=>button.click());};
 try {
  await act(async()=>root.render(<QueryClientProvider client={cache}><ModelProviderSettings settings={settings} compact /></QueryClientProvider>));
  await click('模型与提供方设置');
  const key=document.querySelector<HTMLInputElement>('input[type=password]')!;
  await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(key,'fixture-only-key');key.dispatchEvent(new Event('input',{bubbles:true}));});
  await click('对话与执行');
  expect(document.body.textContent).toContain('制作推荐模型');
  expect(document.querySelector('[role=tabpanel][hidden]')?.id).toContain('connection');
  await click('连接与模型');
  const effort=[...document.querySelectorAll('label')].find(item=>item.querySelector('span')?.textContent==='思考强度')!.querySelector('select')!;
  await act(async()=>{effort.value='high';effort.dispatchEvent(new Event('change',{bubbles:true}));});
  expect(key.value).toBe('fixture-only-key');expect(save).not.toHaveBeenCalled();expect(probe).not.toHaveBeenCalled();expect(models).not.toHaveBeenCalled();
  await click('保存设置');
  expect(save).toHaveBeenCalledWith(expect.objectContaining({api_key:'fixture-only-key',provider:'openai-compatible',reasoning_effort:'high',selector_provider:'codexcli',selector_model:'economy-model'}));
  expect(document.querySelector('dialog')).toBeNull();
  await click('模型与提供方设置');
  expect(document.querySelector<HTMLInputElement>('input[type=password]')!.value).toBe('');
 } finally {await act(async()=>root.unmount());host.remove();cache.clear();vi.restoreAllMocks();}
});

test('server failure offers one-click repair and repeats the connection check',async()=>{
 const settings={provider:'codebuddycli',model:'glm-5.3',base_url:null,api_key_configured:false,api_protocol:'chat-completions',streaming:true,alignment_detail:'standard',reasoning_effort:'medium',agent_timeout_minutes:null,selector_provider:null,selector_model:null} as api.AISettings;
 const probe=vi.spyOn(api,'checkProvider')
  .mockRejectedValueOnce(new ApiError(500,'本地服务处理失败'))
  .mockResolvedValue({provider:'codebuddycli',model:'glm-5.3',api_protocol:'chat-completions',streaming:true,connected:true,mode:'live',latency_ms:12,message:'连接成功'});
 const repair=vi.spyOn(api,'repairLocalApi').mockResolvedValue({state:'ready',message:'本地服务已重启，正在重新检查连接。'});
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);const cache=new QueryClient();
 const click=async(name:string)=>{const button=[...document.querySelectorAll('button')].find(item=>item.getAttribute('aria-label')===name||item.textContent===name)!;expect(button).toBeTruthy();await act(async()=>button.click());};
 try {
  await act(async()=>root.render(<QueryClientProvider client={cache}><ModelProviderSettings settings={settings} compact /></QueryClientProvider>));
  await click('模型与提供方设置');
  await click('检查连接');
  expect(document.body.textContent).toContain('修复并重新检查');
  await click('修复并重新检查');
  expect(repair).toHaveBeenCalledOnce();
  expect(probe).toHaveBeenCalledTimes(2);
  expect(document.body.textContent).toContain('连接成功 12 ms');
 } finally {await act(async()=>root.unmount());host.remove();cache.clear();vi.restoreAllMocks();}
});
