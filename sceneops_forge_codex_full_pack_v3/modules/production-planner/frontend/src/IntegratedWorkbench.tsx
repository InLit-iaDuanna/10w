import { useMemo, useState } from 'react';
import type { IntegratedWorkbenchProps, JsonValue } from '@sceneops/core-ui';
import { createProjectFetch } from '@sceneops/api-client';
import { IntegratedDraftForm, useWorkbenchDraft } from '@sceneops/workbench-ui';
import { PlanningPanel } from './PlanningPanel';
import { createPlanningClient } from './generated/lab-client';

type TaskDraft = { task_id: string; title: string; owner: string; depends_on: string };
export default function IntegratedWorkbench(props: IntegratedWorkbenchProps) {
  const draft = useWorkbenchDraft(props);
  const [taskTitle, setTaskTitle] = useState('');
  const client = useMemo(() => createPlanningClient('', createProjectFetch(props.project.project_id)), [props.project.project_id]);
  const tasks = (Array.isArray(draft.payload.tasks) ? draft.payload.tasks : []) as TaskDraft[];
  const updateTasks = (value: TaskDraft[]) => draft.update({ tasks: value as unknown as JsonValue });
  return <>
    <IntegratedDraftForm title="项目设计与生产计划" draft={draft} fields={[
      { key: 'brief', label: '项目简述', multiline: true }, { key: 'audience', label: '目标玩家' },
      { key: 'core_loop', label: '核心玩法循环', multiline: true }, { key: 'feature_spec', label: '功能规格', multiline: true },
      { key: 'acceptance', label: '人工验收标准', multiline: true }, { key: 'plan_id', label: '已有领域计划 ID（可选）' },
    ]}>
      <h4>自己的任务草稿</h4>
      <div><input aria-label="新任务标题" value={taskTitle} onChange={event => setTaskTitle(event.target.value)}/><button type="button" disabled={!taskTitle.trim()} onClick={() => { updateTasks([...tasks, { task_id: `task_${crypto.randomUUID()}`, title: taskTitle.trim(), owner: '', depends_on: '' }]); setTaskTitle(''); }}>添加任务</button></div>
      {tasks.map(task => <fieldset key={task.task_id}><legend><button type="button" onClick={() => props.onContextChange({ activeTaskId: task.task_id })}>{task.title}</button></legend>
        <label>标题<input value={task.title} onChange={event => updateTasks(tasks.map(item => item.task_id === task.task_id ? { ...item, title: event.target.value } : item))}/></label>
        <label>负责人<input value={task.owner} onChange={event => updateTasks(tasks.map(item => item.task_id === task.task_id ? { ...item, owner: event.target.value } : item))}/></label>
        <label>前置任务<select value={task.depends_on} onChange={event => updateTasks(tasks.map(item => item.task_id === task.task_id ? { ...item, depends_on: event.target.value } : item))}><option value="">无</option>{tasks.filter(item => item.task_id !== task.task_id).map(item => <option key={item.task_id} value={item.task_id}>{item.title}</option>)}</select></label>
        <button type="button" onClick={() => updateTasks(tasks.filter(item => item.task_id !== task.task_id).map(item => item.depends_on === task.task_id ? { ...item, depends_on: '' } : item))}>移除草稿任务</button>
      </fieldset>)}
      <p>任务尚未确认、未启动代理或生产作业；依赖与验收需人工确认。</p>
    </IntegratedDraftForm>
    {typeof props.document.payload.plan_id === 'string' && props.document.payload.plan_id && <PlanningPanel client={client} planId={props.document.payload.plan_id}/>}
  </>;
}
