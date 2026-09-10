import {agentTasks} from './client';

type Runtime = Pick<typeof agentTasks, 'list' | 'gameStatus' | 'gameOperation' | 'updateProjectDemo'>;

export async function launchLatestGame(projectId: string, runtime: Runtime = agentTasks) {
  const {tasks} = await runtime.list(projectId);
  const task = [...tasks].filter(item => item.grant && item.authorization_card.allow_game_execution
    && ['project-demo', 'project-demo-agent'].includes(item.authorization_card.task_profile))
    .sort((a,b) => b.created_at.localeCompare(a.created_at))[0];
  if (!task) throw new Error('当前项目还没有游戏版本，请先完成初版制作。');
  const state = await runtime.gameStatus(task.id);
  if (state.build?.status === 'succeeded' && !state.build.source_stale
      && state.preview?.status === 'running' && !state.preview.source_stale
      && state.preview.preview_url && state.preview.build_run_id === state.build.id) return task.id;
  if (task.owner_pid != null || ['running','queued','cancel_pending'].includes(task.status)) {
    throw new Error('当前项目正在制作，请等待本轮结束后启动最新版本。');
  }
  if (state.build?.status !== 'succeeded' || state.build.source_stale) {
    const updated = await runtime.updateProjectDemo(task.id);
    return updated.id;
  }
  if (state.preview?.status !== 'running' || state.preview.source_stale
      || state.preview.build_run_id !== state.build.id) {
    const started = await runtime.gameOperation(task.id, 'preview_start');
    if (started.preview?.status !== 'running' || !started.preview.preview_url) {
      throw new Error(started.preview?.log || '最新版本未能启动，请查看运行控制与构建记录。');
    }
  }
  return task.id;
}
