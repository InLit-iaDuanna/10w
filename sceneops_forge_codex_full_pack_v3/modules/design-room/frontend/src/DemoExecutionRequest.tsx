import { useState } from 'react';

/** The explicit conversation action authorizes this aligned execution. */
export function DemoExecutionRequest({ alignmentId, prepare, mode = 'full-access' }: {
  alignmentId: string; prepare: () => Promise<void>;
  mode?: 'full-access' | 'typed-tools' | 'project-demo-agent';
}) {
  const [started, setStarted] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const request = async () => {
    setError(''); setPending(true);
    try { await prepare(); setStarted(alignmentId); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setPending(false); }
  };
  if (started === alignmentId) return null;
  const typed = mode === 'typed-tools';
  const projectAgent = mode === 'project-demo-agent';
  return <div className="journey-execution-consent"><div><strong>准备开始执行</strong><p>{projectAgent ? '制作模型将按已确认方向选择内容与源码修改，再用登记工程完成检查、构建和试玩更新。' : typed ? '系统将按固定步骤物化内容、构建并更新同一试玩。' : 'Agent 将在当前工程继续完成已对齐的目标。'}</p></div><button type="button" disabled={pending} onClick={() => void request()}>
    {pending ? '正在开始…' : projectAgent ? '确认范围并让 Agent 制作' : typed ? '确认范围并制作初版' : '允许 Agent 完全访问并开始'}</button>
    <details><summary>权限范围与预算</summary><small>{projectAgent ? '仅操作当前登记项目的资产、场景和普通游戏源码；派生运行输入与构建产物不作为编辑源。整个任务累计最多 28 次模型请求、32 个类型化动作和 30 分钟；追加修改与修复不重置预算或期限，不提交或发布。' : typed ? '仅操作当前登记项目的门配方、场景实例、行为参数、派生运行输入和固定工程命令。最多 32 个步骤、20 分钟；修复不重置预算或期限，不提交或发布。' : 'Agent 可读写文件、运行命令和访问网络；当前目录不是系统沙箱。仅授权本次项目任务，费用可能未知。同一对话上一轮若已停止，将保留当前文件继续。'}</small></details>
    {error && <p role="alert">{error}</p>}</div>;
}
