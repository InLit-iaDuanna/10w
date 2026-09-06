import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import type { CurrentModelingAssetInput } from './CurrentModelingTool.tsx';
import { journeyClient, journeyKey, type JourneyCommand, type JourneyMessage } from './journey-client.ts';

export function CurrentWorldTool({projectId, renderEnvironment, renderModel}: {
  projectId:string;
  renderEnvironment():ReactNode;
  renderModel(input:CurrentModelingAssetInput & {presentation:'scene'}):ReactNode;
}) {
  const cache = useQueryClient();
  const query = useQuery({queryKey:journeyKey(projectId),queryFn:({signal}) => journeyClient.get(projectId,signal),retry:false});
  const mutation = useMutation({
    mutationFn: (input:Pick<JourneyCommand,'operation'> & Partial<JourneyCommand>) => {
      const state = query.data;
      if (!state) throw new Error('制作状态尚未读取。');
      return journeyClient.command(projectId,{...input,request_id:crypto.randomUUID(),expected_revision:state.revision,
        text:input.text ?? '',accept_assumptions:input.accept_assumptions ?? false,
        context_draft:input.context_draft ?? state.composer_draft ?? ''});
    },
    onSuccess:state => cache.setQueryData(journeyKey(projectId),state),
  });
  if (query.isPending) return <p role="status">读取当前 3D 世界状态…</p>;
  if (query.error || !query.data) return <p role="alert">{query.error?.message ?? '3D 世界状态读取失败。'} <button onClick={() => void query.refetch()}>重试</button></p>;
  const state = query.data;
  const modeling = state.modeling_sessions?.find(item => item.id === state.active_modeling_id);
  if (!modeling) return renderEnvironment();
  const act = (operation:JourneyCommand['operation'], extra:Partial<JourneyCommand> = {}) => mutation.mutate({operation,...extra});
  return <>{renderModel({projectId,cardId:modeling.card_id,source:modeling.source,sessionId:modeling.id,
    messages:(modeling.messages ?? []).map((message:JourneyMessage) => ({id:message.id,role:message.role,text:message.text,
      ...(message.reply_to ? {replyTo:message.reply_to} : {}),...(message.modeling_block ? {modelingBlock:message.modeling_block} : {})})),
    observeConversation:true,presentation:'scene',
    onCreateAnother:() => act('new_modeling',{card_id:modeling.card_id,model_source:'create'}),
    onOpenEnvironment:() => act('close_modeling')})}
    {mutation.error && <p role="alert">{mutation.error.message}</p>}</>;
}
