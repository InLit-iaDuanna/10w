import { ComposerMenu } from '../../../../../packages/core-ui/frontend/src/index.ts';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiKeys, readModels, readSettings, saveSettings } from './aiClient.ts';
import { ModelBrandMark, modelPresentation, REASONING_EFFORT_OPTIONS, type ReasoningEffort } from './ModelBrandMark.tsx';
import { ModelProviderSettings } from './ModelProviderSettings.tsx';

export function useAIAvailability() {
  const models = useQuery({ queryKey: aiKeys.models, queryFn: ({ signal }) => readModels(signal), retry: false });
  const settings = useQuery({ queryKey: aiKeys.settings, queryFn: ({ signal }) => readSettings(signal), retry: false });
  return { models, settings, ready: !!models.data?.available && !!settings.data && !settings.isError };
}

export function UnifiedModelPicker({ disabled = false, compact = false }: { disabled?: boolean; compact?: boolean }) {
  const cache = useQueryClient();
  const { models, settings } = useAIAvailability();
  const update = useMutation({ mutationFn: saveSettings,
    onSuccess: (value) => { cache.setQueryData(aiKeys.settings, value); } });
  const provider = settings.data?.provider ?? 'codebuddycli';
  const modelsForProvider = models.data?.models.filter(model => model.provider === provider) ?? [];
  const selectedId = settings.data?.model ?? 'cli-default';
  const modelOptions = [
    ...(settings.data && !modelsForProvider.some(model => model.id === selectedId)
      ? [{ id: selectedId, label: selectedId }]
      : []),
    ...modelsForProvider,
  ];
  const modelBusy = disabled || !models.data || !settings.data || update.isPending;
  const error = models.error ?? settings.error ?? update.error;

  function selectReasoningEffort(value: ReasoningEffort) {
    if (value !== (settings.data?.reasoning_effort ?? 'low')) update.mutate({ reasoning_effort: value });
  }

  return <div className={`unified-ai-model${compact ? ' is-compact' : ''}`} data-provider={provider}>
    <div className="unified-ai-model-controls" title={models.isPending || settings.isPending ? '正在读取 AI 配置…' : models.data?.message}>
      <ComposerMenu label="当前模型" value={selectedId} disabled={modelBusy}
        onChange={id=>{if(id!==selectedId)update.mutate({model:id});}}
        options={modelOptions.map(model=>{const presentation=modelPresentation(model.id,provider,model.label);return {value:model.id,label:presentation.label,description:model.id,icon:<ModelBrandMark brand={presentation.brand} label={presentation.label}/>};})} />
      {settings.data?.provider !== 'codexcli' && <ComposerMenu label="思考强度" value={settings.data?.reasoning_effort ?? 'low'} disabled={modelBusy}
        onChange={value=>selectReasoningEffort(value as ReasoningEffort)}
        options={REASONING_EFFORT_OPTIONS.map(option=>({value:option.value,label:option.label}))} />}
      {settings.data && <ModelProviderSettings settings={settings.data} disabled={disabled || update.isPending} compact={compact} />}
    </div>
    {(!compact || models.data?.available === false) && <small><i aria-hidden="true" />{models.isPending || settings.isPending ? '正在读取 AI 配置…' : models.data?.message}</small>}
    {error && <p role="alert">{error.message} <button type="button" onClick={() => {
      void models.refetch(); void settings.refetch(); update.reset();
    }}>重新读取</button></p>}
  </div>;
}
