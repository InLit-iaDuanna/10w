import assert from 'node:assert/strict';
import test from 'node:test';
import {createLookdevClient} from '../src/lookdev-client.ts';
test('durable turns use the project-scoped shared client and preserve finish status',async()=>{
  const original=globalThis.fetch;
  const calls:{url:string;body:unknown;project:string|null}[]=[];
  globalThis.fetch=async(input,init)=>{
    calls.push({url:String(input),body:init?.body?JSON.parse(String(init.body)):undefined,project:new Headers(init?.headers).get('X-SceneOps-Project')});
    return new Response(JSON.stringify(String(input).endsWith('/turns')?[]:{id:'turn-1',status:'applied'}),{status:200,headers:{'Content-Type':'application/json'}});
  };
  try{
    const api=createLookdevClient('project-1');
    assert.deepEqual(await api.history(),[]);
    await api.finish('turn-1',{status:'applied',summary:'GPU accepted'});
    assert.equal(calls[1].url,'/api/lookdev/project-1/turns/turn-1/finish');
    assert.equal(calls[1].project,'project-1');
    assert.deepEqual(calls[1].body,{status:'applied',summary:'GPU accepted'});
    globalThis.fetch=async()=>new Response(JSON.stringify({message:'version conflict'}),{status:409});
    await assert.rejects(api.history(),/version conflict/);
  }finally{globalThis.fetch=original;}
});
