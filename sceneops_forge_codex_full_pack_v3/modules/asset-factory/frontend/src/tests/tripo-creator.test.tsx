import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { TripoCreator } from '../TripoCreator';
const {render,screen,fireEvent,waitFor,cleanup}=createRequire(resolve('modules/character-animation/frontend/package.json'))('@testing-library/react');
const state=vi.hoisted(()=>({configured:false,requests:[] as {url:string;options:any}[]}));
vi.mock('../CardModelPreview',()=>({CardModelPreview:()=> <div>模型预览</div>}));
vi.mock('@sceneops/api-client',()=>({requestJson:vi.fn(async(url:string,options:any={})=>{
 state.requests.push({url,options});
 if(url.endsWith('/tripo/settings')){
  if(options.body)state.configured=true;
  return {configured:state.configured,model_version:'v3.1-20260211',available_models:['v3.1-20260211','v2.5-20250123']};
 }
 if(url.includes('/tripo/jobs?'))return [];
 if(url.endsWith('/tripo/jobs')&&options.body)return {id:'job-1',status:'queued',progress:0,task_id:'remote-1'};
 if(url.endsWith('/tripo/jobs/job-1'))return {id:'job-1',status:'running',progress:42,task_id:'remote-1'};
 throw new Error('Unexpected '+url);
})}));
vi.mock('../cardAssetClient',()=>({cardAssetClient:{reference:vi.fn(async()=>({id:'reference-owned'}))},cardAssetKey:()=>['card-assets','p','c']}));
beforeEach(()=>{state.configured=false;state.requests=[];vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function mount(){const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});render(<QueryClientProvider client={client}><TripoCreator projectId="p" cardId="c" sessionId="s" initialPrompt="a small tree" onReady={()=>{}}/></QueryClientProvider>);return client;}
it('requires configuration and an explicit generation click, and never places the key in the generation request',async()=>{
 const client=mount();await waitFor(()=>expect(screen.getByRole('button',{name:'保存配置'})).toBeTruthy());
 expect(screen.getByRole('button',{name:'使用 Tripo 生成模型'}).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('API Key'),{target:{value:'fixture-private-key'}});
 fireEvent.click(screen.getByRole('button',{name:'保存配置'}));
 await waitFor(()=>expect(screen.getByRole('button',{name:'使用 Tripo 生成模型'}).disabled).toBe(false));
 expect(screen.getByLabelText('API Key').value).toBe('');
 expect(state.requests.filter(r=>r.url.endsWith('/tripo/jobs')&&r.options.body)).toHaveLength(0);
 fireEvent.click(screen.getByRole('button',{name:'使用 Tripo 生成模型'}));
 await waitFor(()=>expect(state.requests.filter(r=>r.url.endsWith('/tripo/jobs')&&r.options.body)).toHaveLength(1));
 const body=state.requests.find(r=>r.url.endsWith('/tripo/jobs')&&r.options.body)!.options.body;
 expect(body.prompt).toBe('a small tree');expect(body.session_id).toBe('s');expect(body.api_key).toBeUndefined();
 await waitFor(()=>expect(screen.getByText(/remote-1/)).toBeTruthy());client.clear();
});
it('does not upload a selected image until the user submits it',async()=>{
 state.configured=true;const client=mount();await waitFor(()=>expect(screen.getByRole('button',{name:'使用 Tripo 生成模型'}).disabled).toBe(false));
 fireEvent.click(screen.getByRole('button',{name:'图片生成'}));
 expect(screen.getByRole('button',{name:'使用 Tripo 生成模型'}).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('参考图片'),{target:{files:[new File(['fixture'],'image.png',{type:'image/png'})]}});
 expect(state.requests.filter(r=>r.options.body)).toHaveLength(0);
 fireEvent.click(screen.getByRole('button',{name:'使用 Tripo 生成模型'}));
 await waitFor(()=>expect(state.requests.find(r=>r.url.endsWith('/tripo/jobs')&&r.options.body)?.options.body.reference_id).toBe('reference-owned'));client.clear();
});
