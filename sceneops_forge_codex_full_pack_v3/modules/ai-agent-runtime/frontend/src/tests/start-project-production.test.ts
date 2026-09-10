import assert from 'node:assert/strict';
import test from 'node:test';
import { startProjectProduction } from '../startProjectProduction';
import type { agentTasks, AgentTask } from '../client';

const input = {projectId:'project', directionId:'direction', goal:'制作风暴灯塔岛', policy:'full-access' as const};
const provider = {provider:'codebuddycli', model:'configured-model'};
function fixture(records: AgentTask[] = []) {
  const calls: {operation:string; id?:string; body:any}[] = [];
  const tasks: Pick<typeof agentTasks, 'list'|'prepare'|'authorize'|'continueProjectDemo'> = {
    list: async () => ({tasks:records}),
    prepare: async body => {calls.push({operation:'prepare',body});return {id:'prepared'} as AgentTask;},
    authorize: async (id,body) => {calls.push({operation:'authorize',id,body});return {} as AgentTask;},
    continueProjectDemo: async (id,body) => {calls.push({operation:'continue',id,body});return {} as AgentTask;},
  };
  return {tasks,calls};
}
function nativeTask(id:string, createdAt:string, overrides:Partial<AgentTask>={}):AgentTask {
  return {id,created_at:createdAt,provider_id:provider.provider,provider_model:provider.model,
    status:'review_required',observations:{native_production:true,native_session_id:`session-${id}`},grant:{task_id:id},
    authorization_card:{task_profile:'project-demo-agent',alignment_id:'direction'},...overrides} as AgentTask;
}

test('scoped and full policies both prepare native production without bypassing brief confirmation', async () => {
  for (const policy of ['ask','full-access'] as const) {
    const {tasks,calls}=fixture();
    await startProjectProduction({...input,policy},provider,tasks);
    assert.deepEqual(calls.map(call=>call.operation),['prepare']);
    assert.equal(calls[0]!.body.native_production,true);
    assert.equal(calls[0]!.body.execution_mode,'agent-full-access');
    assert.equal(calls[0]!.body.permission_mode,policy==='ask'?'scoped':'full');
    assert.equal(calls[0]!.body.allow_game_execution,true);
    assert.equal(calls[0]!.body.allow_model_image_input,true);
  }
  const codex=fixture();
  await startProjectProduction(input,{provider:'codexcli',model:'configured-model'},codex.tasks);
  assert.deepEqual(codex.calls.map(call=>call.operation),['prepare']);
});

test('continuation selects the latest matching native harness session and may switch its model',async()=>{
  const {tasks,calls}=fixture([
    nativeTask('old','2026-09-08'),nativeTask('latest','2026-09-09'),
    nativeTask('other-model','2026-09-10',{provider_model:'other'}),
    nativeTask('typed','2026-09-11',{observations:{}}),
    nativeTask('unconfirmed','2026-09-12',{grant:null}),
  ]);
  await startProjectProduction({...input,continuation:true,goal:'移动太慢'},provider,tasks);
  assert.equal(calls.length,1);
  assert.equal(calls[0]!.operation,'continue');
  assert.equal(calls[0]!.id,'other-model');
  assert.equal(calls[0]!.body.goal,'移动太慢');
  assert.equal(typeof calls[0]!.body.request_id,'string');
});

test('a native round awaiting review continues the same CLI conversation',async()=>{
  const {tasks,calls}=fixture([nativeTask('limited','2026-09-09',{status:'needs_approval'})]);
  await startProjectProduction({...input,continuation:true,goal:'额度恢复后继续完成'},provider,tasks);
  assert.deepEqual(calls.map(call=>call.operation),['continue']);
  assert.equal(calls[0]!.id,'limited');
});

test('missing matching continuation prepares a brief without automatic authorization',async()=>{
  const {tasks,calls}=fixture([nativeTask('other','2026-09-09',{provider_id:'codexcli'})]);
  await startProjectProduction({...input,continuation:true},provider,tasks);
  assert.deepEqual(calls.map(call=>call.operation),['prepare']);
});

test('OpenAI-compatible production uses the Codex harness route',async()=>{
  const {tasks,calls}=fixture();
  await startProjectProduction(input,{provider:'openai-compatible',model:'model'},tasks);
  assert.deepEqual(calls.map(call=>call.operation),['prepare']);
  assert.equal(calls[0]!.body.native_production,true);
});

test('unsupported provider is rejected before preparing or authorizing',async()=>{
  const {tasks,calls}=fixture();
  await assert.rejects(startProjectProduction(input,{provider:'unsupported',model:'model'},tasks),/harness/);
  assert.equal(calls.length,0);
});

test('preparation failure propagates without authorization or provider retry',async()=>{
  const {tasks,calls}=fixture();
  tasks.prepare=async()=>{throw new Error('配置已改变');};
  await assert.rejects(startProjectProduction(input,provider,tasks),/配置已改变/);
  assert.equal(calls.length,0);
});

test('production card continues the same project session and never creates a replacement task',async()=>{
  const {tasks,calls}=fixture([nativeTask('latest','2026-09-09')]);
  await startProjectProduction({...input,continuation:true,planningCardId:'weapon',goal:'把枪身改为绿色'},provider,tasks);
  assert.equal(calls[0]!.operation,'continue');
  assert.equal(calls[0]!.id,'latest');
  assert.equal(calls[0]!.body.planning_card_id,'weapon');
  const missing=fixture();
  await assert.rejects(startProjectProduction({...input,continuation:true,planningCardId:'weapon'},provider,missing.tasks),/没有可续改/);
  assert.equal(missing.calls.length,0);
});
