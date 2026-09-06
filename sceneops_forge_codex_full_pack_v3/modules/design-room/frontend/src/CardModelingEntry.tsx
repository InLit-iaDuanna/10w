import type { PlanningJourney, JourneyCommand } from './journey-client';

export function CardModelingEntry({ state, busy, onCommand, onOpenEnvironment }: {
  state: PlanningJourney; busy: boolean;
  onCommand: (operation: JourneyCommand['operation'], extra?: Partial<JourneyCommand>) => void;
  onOpenEnvironment?: () => void;
}) {
  const card = (state.cards ?? []).find(item => item.id === state.active_card_id);
  const sessions = (state.modeling_sessions ?? []).filter(item => item.card_id === state.active_card_id);
  const createSessions = sessions.filter(item => item.source === 'create');
  const current = sessions.find(item => item.id === state.active_modeling_id);
  if (!state.active_card_id || !card) return null;
  const workflow = card.id === 'core-gameplay' ? 'gameplay' : card.id === 'growth-feedback' ? 'experience' : card.id === 'demo-delivery' ? 'delivery' : 'world_3d';
  if (workflow !== 'world_3d') {
    const copy = {
      gameplay: ['核心玩法工作流', '在这一条线里统一完成控制、战斗、敌人逻辑、武器、波次与经验循环。'],
      experience: ['成长与反馈工作流', '在这一条线里统一完成升级、HUD、视觉反馈、音效与特效。'],
      delivery: ['Demo 完成工作流', '在这一条线里串联完整单局、性能检查、构建与交付；何时试玩由你决定。'],
    }[workflow];
    return <section className="journey-modeling-entry" aria-label={copy[0]}>
      <div className="journey-modeling-heading"><strong>{copy[0]}</strong></div>
      <p>{copy[1]}</p>
      <small>继续使用下方唯一主对话；不会再展开一排内部实现卡片。</small>
    </section>;
  }
  return <section className="journey-modeling-entry" aria-label="卡片模型工作流">
    <div className="journey-modeling-heading"><strong>{current ? current.source === 'create' ? '新建模型 · 需求对话' : '导入已有模型' : '选择这张卡片的下一步'}</strong>
      {current && <button disabled={busy} onClick={() => onOpenEnvironment ? onOpenEnvironment() : onCommand('close_modeling')}>{onOpenEnvironment ? '返回 3D 世界' : '返回卡片'}</button>}</div>
    {!current && <><div className="journey-source-options">
      <button disabled={busy} onClick={() => onCommand('choose_model_source', { card_id: state.active_card_id, model_source: 'import' })}><strong>导入已有模型</strong><small>GLB / FBX · 检查、预览与归一化</small></button>
      <button disabled={busy} onClick={() => onCommand(createSessions.length ? 'new_modeling' : 'choose_model_source', { card_id: state.active_card_id, model_source: 'create' })}><strong>新建模型</strong><small>描述或参考图 → 实时版本 → 资产库</small></button>
      {onOpenEnvironment && <button disabled={busy} onClick={onOpenEnvironment}><strong>搭建环境</strong><small>资产库 → 人工摆放 / AI 搭建</small></button>}
    </div>{!!sessions.length && <div className="journey-actions">{sessions.map((item,index) => <button key={item.id} disabled={busy} onClick={() => onCommand('open_modeling', { card_id: item.card_id, modeling_id: item.id })}>继续{item.source === 'create' ? `建模对话 ${sessions.slice(0,index + 1).filter(value => value.source === 'create').length}` : '模型导入'}{item.messages?.length ? ` · ${item.messages.length} 条消息` : ''}</button>)}</div>}</>}
    {current?.source === 'create' && <p>每轮回答都会追加一个真实模型草稿；右侧 Three.js 预览自动刷新，旧版本保留。</p>}
    {current?.source === 'import' && <p>在右侧选择 GLB 或 FBX，导入后立即检查和预览。</p>}
    <small>产物写入当前 Git 卡片分支，不自动提交或合并。</small>
  </section>;
}
