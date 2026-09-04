import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiKeys, readModels, readSettings, saveSettings } from './aiClient.ts';

export function useAIAvailability() {
  const models = useQuery({ queryKey: aiKeys.models, queryFn: ({ signal }) => readModels(signal), retry: false });
  const settings = useQuery({ queryKey: aiKeys.settings, queryFn: ({ signal }) => readSettings(signal), retry: false });
  return { models, settings, ready: !!models.data?.available && !!settings.data && !settings.isError };
}

export function UnifiedModelPicker({ disabled = false }: { disabled?: boolean }) {
  const cache = useQueryClient();
  const { models, settings } = useAIAvailability();
  const update = useMutation({ mutationFn: saveSettings,
    onSuccess: (value) => { cache.setQueryData(aiKeys.settings, value); } });
  const error = models.error ?? settings.error ?? update.error;
  return <div className="unified-ai-model">
    <label>模型 <select aria-label="CodeBuddy 模型" value={settings.data?.model ?? 'cli-default'}
      disabled={disabled || !models.data || !settings.data || update.isPending}
      onChange={(event) => update.mutate({ model: event.target.value })}>
      {!models.data && <option value="cli-default">CLI 默认模型</option>}
      {models.data?.models.map((model) => <option key={model.id} value={model.id}>{model.label}</option>)}
    </select></label>
    <small>{models.isPending || settings.isPending ? '正在读取 AI 配置…' : models.data?.message}</small>
    {error && <p role="alert">{error.message} <button type="button" onClick={() => {
      void models.refetch(); void settings.refetch(); update.reset();
    }}>重新读取</button></p>}
  </div>;
}
