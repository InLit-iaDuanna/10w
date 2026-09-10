import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { CardModelingEntry } from './CardModelingEntry.tsx';
import {
  journeyClient,
  journeyKey,
  type JourneyCommand,
  type JourneyMessage,
} from './journey-client.ts';
import './current-modeling-tool.css';

export interface CurrentModelingAssetInput {
  projectId: string;
  cardId: string;
  source: 'import' | 'create';
  sessionId: string;
  messages: Array<{
    id: string;
    role: string;
    text: string;
    replyTo?: string;
    modelingBlock?: string;
  }>;
  observeConversation: boolean;
  onCreateAnother(): void;
  onOpenEnvironment(): void;
}

export function CurrentModelingTool({
  projectId,
  renderAssetWorkflow,
  onOpenEnvironment,
  projectAssets,
}: {
  projectId: string | null;
  projectAssets?: ReactNode;
  renderAssetWorkflow(input: CurrentModelingAssetInput): ReactNode;
  onOpenEnvironment(): void;
}) {
  const cache = useQueryClient();
  const query = useQuery({
    queryKey: journeyKey(projectId ?? 'no-project'),
    queryFn: ({ signal }) => journeyClient.get(projectId!, signal),
    enabled: !!projectId,
    retry: false,
  });
  const mutation = useMutation({
    mutationFn: (input: Pick<JourneyCommand, 'operation'> & Partial<JourneyCommand>) => {
      const state = query.data;
      if (!projectId || !state) throw new Error('请先选择一个文件夹项目。');
      const activeSession = state.modeling_sessions?.find(item => item.id === state.active_modeling_id);
      return journeyClient.command(projectId, {
        ...input,
        request_id: crypto.randomUUID(),
        expected_revision: state.revision,
        text: input.text ?? '',
        accept_assumptions: input.accept_assumptions ?? false,
        context_draft: input.context_draft ?? activeSession?.composer_draft ?? state.composer_draft ?? '',
      });
    },
    onSuccess: state => cache.setQueryData(journeyKey(state.project_id), state),
  });
  if (!projectId) return <ToolState title="尚未选择项目">先通过右上角“本地项目”选择一个文件夹。</ToolState>;
  if (query.isPending) return <ToolState title="正在读取">读取当前制作卡片与模型版本…</ToolState>;
  if (query.error || !query.data) return <ToolState title="读取失败" error>{query.error?.message ?? '策划数据不存在。'} <button onClick={() => void query.refetch()}>重试</button></ToolState>;

  const state = query.data;
  const activeCard = state.cards?.find(card => card.id === state.active_card_id);
  const modeling = state.modeling_sessions?.find(item => item.id === state.active_modeling_id);
  const act = (operation: JourneyCommand['operation'], extra: Partial<JourneyCommand> = {}) => mutation.mutate({ operation, ...extra });
  const createAnother = () => activeCard && act('new_modeling', { card_id: activeCard.id, model_source: 'create' });
  const returnToEnvironment = () => {
    if (modeling) act('close_modeling');
    onOpenEnvironment();
  };
  return <section className="current-modeling-tool" aria-label="模型与资产">
    <header><div><strong>模型与资产</strong><small>主对话负责描述，这里负责选择、预览、归一化和入库</small></div><span>Three.js / Blender</span></header>
    <div className="current-modeling-scroll">{projectAssets}
      {!state.cards?.length && <ToolState title="还没有制作卡片">先在主对话完成 idea、细节对齐和制作卡片，再进入建模。</ToolState>}
      {!!state.cards?.length && !activeCard && <section className="current-modeling-card-list">
        <strong>选择要制作的卡片</strong><small>选择后会进入该卡片已经准备好的 Git 分支。</small>
        <div>{state.cards.map(card => <button key={card.id} disabled={mutation.isPending}
          onClick={() => act('select_card', { card_id: card.id })}><strong>{card.title}</strong><span>{card.description}</span></button>)}</div>
      </section>}
      {activeCard && <>
        <div className="current-modeling-context"><div><small>当前制作卡片</small><strong>{activeCard.title}</strong></div><button disabled={mutation.isPending} onClick={() => act('clear_card')}>更换卡片</button></div>
        <CardModelingEntry state={state} busy={mutation.isPending} onCommand={act} onOpenEnvironment={returnToEnvironment} />
        {modeling && <>
          {modeling.source === 'create' && <p className="current-modeling-guidance">在中央主对话继续描述或修改模型；每次回复会生成一个可切换的新版本。</p>}
          {renderAssetWorkflow({
            projectId,
            cardId: modeling.card_id,
            source: modeling.source,
            sessionId: modeling.id,
            messages: (modeling.messages ?? []).map((message: JourneyMessage) => ({
              id: message.id,
              role: message.role,
              text: message.text,
              ...(message.reply_to ? { replyTo: message.reply_to } : {}),
              ...(message.modeling_block ? { modelingBlock: message.modeling_block } : {}),
            })),
            observeConversation: false,
            onCreateAnother: createAnother,
            onOpenEnvironment: returnToEnvironment,
          })}
        </>}
      </>}
      {mutation.error && <p className="current-modeling-error" role="alert">{mutation.error.message}</p>}
    </div>
  </section>;
}

function ToolState({ title, error = false, children }: { title: string; error?: boolean; children: ReactNode }) {
  return <section className="current-modeling-state" role={error ? 'alert' : 'status'}><strong>{title}</strong><p>{children}</p></section>;
}
