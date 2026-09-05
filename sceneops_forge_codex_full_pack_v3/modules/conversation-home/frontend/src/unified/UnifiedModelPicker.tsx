import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiKeys, readModels, readSettings, saveSettings } from './aiClient.ts';
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
  const error = models.error ?? settings.error ?? update.error;
  return <div className={`unified-ai-model${compact ? ' is-compact' : ''}`} data-provider={provider}>
    <div className="unified-ai-model-controls" title={models.isPending || settings.isPending ? '正在读取 AI 配置…' : models.data?.message}>
      <label><span>模型</span><select aria-label="当前模型" value={settings.data?.model ?? 'cli-default'}
        disabled={disabled || !models.data || !settings.data || update.isPending}
        onChange={(event) => update.mutate({ model: event.target.value })}>
        {!models.data && <option value="cli-default">CLI 默认模型</option>}
        {settings.data && !modelsForProvider.some(model => model.id === settings.data?.model) && <option value={settings.data.model}>{settings.data.model}</option>}
        {modelsForProvider.map((model) => <option key={model.id} value={model.id}>{model.label}</option>)}
      </select></label>
      {settings.data && <ModelProviderSettings settings={settings.data} disabled={disabled || update.isPending} compact={compact} />}
    </div>
    {(!compact || models.data?.available === false) && <small><i aria-hidden="true" />{models.isPending || settings.isPending ? '正在读取 AI 配置…' : models.data?.message}</small>}
    {error && <p role="alert">{error.message} <button type="button" onClick={() => {
      void models.refetch(); void settings.refetch(); update.reset();
    }}>重新读取</button></p>}
  </div>;
}
