import { agentTasks } from './client';

type Input = {
  projectId: string; directionId: string; goal: string;
  policy: 'ask' | 'full-access'; continuation?: boolean | undefined;
  inputPaths?: string[] | undefined;
  planningCardId?: string | undefined;
};
type Provider = {provider: string; model: string};
type Tasks = Pick<typeof agentTasks, 'list' | 'prepare' | 'authorize' | 'continueProjectDemo'>;

/** Resolve execution before preparing the server-owned authorization card. */
export async function startProjectProduction(input: Input, provider: Provider, tasks: Tasks = agentTasks) {
  const {projectId, directionId, goal, policy, continuation, inputPaths = []} = input;
  if (!['codexcli', 'codebuddycli', 'openai-compatible'].includes(provider.provider)) {
    throw new Error('项目制作需要 Codex harness 或 CodeBuddy harness。');
  }
  if (continuation) {
    const records = await tasks.list(projectId);
    const task = [...records.tasks].sort((a,b) => b.created_at.localeCompare(a.created_at)).find(item =>
      item.observations.native_production === true
      && item.authorization_card.alignment_id === directionId
      && item.provider_id === provider.provider
      && item.grant
      && typeof item.observations.native_session_id === 'string' && item.observations.native_session_id
      && ['completed','review_required','needs_approval','failed','interrupted','cancelled'].includes(item.status));
    if (task) {
      await tasks.continueProjectDemo(task.id, {request_id:crypto.randomUUID(), goal, input_paths:inputPaths, planning_card_id:input.planningCardId});
      return;
    }
  }
  if (input.planningCardId) throw new Error('没有可续改的当前制作会话，请检查执行器设置与最新制作记录。');
  await tasks.prepare({project_id:projectId, goal, task_profile:'project-demo-agent',
    native_production:true, permission_mode:policy === 'full-access' ? 'full' : 'scoped',
    execution_mode:'agent-full-access', allow_image_generation:false,
    allow_playtest:false, allow_game_execution:true, allow_dependency_install:true,
    include_demo_assets:true, allow_browser_observation:true,
    allow_browser_interaction:true, allow_model_image_input:true, alignment_id:directionId,
    input_paths:inputPaths});
}
