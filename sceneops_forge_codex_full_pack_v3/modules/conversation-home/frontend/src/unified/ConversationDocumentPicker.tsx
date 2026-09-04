import { useQuery } from '@tanstack/react-query';
import { workspaceClient, type ModuleDocument, type ModuleId } from '@sceneops/workspace-client';

export function useConversationDocument(projectId: string | null, moduleId: ModuleId | '') {
  return useQuery({ queryKey: ['workspace-document', projectId, moduleId],
    queryFn: () => workspaceClient.document(projectId!, moduleId as ModuleId),
    enabled: !!projectId && !!moduleId, retry: false });
}

export function ConversationDocumentPicker({ projectId, selected, onChange, disabled, document, error, loading, retry }: {
  projectId: string | null; selected: ModuleId | ''; onChange: (id: ModuleId | '') => void;
  disabled: boolean; document?: ModuleDocument; error: Error | null; loading: boolean; retry: () => void;
}) {
  const modules = useQuery({ queryKey: ['workspace-modules'], queryFn: workspaceClient.modules,
    enabled: !!projectId, retry: false });
  if (!projectId) return null;
  return <div className="unified-ai-document">
    <label>附带已保存模块草稿 <select value={selected} disabled={disabled || !modules.data}
      onChange={event => onChange(event.target.value as ModuleId | '')}>
      <option value="">不附带草稿</option>
      {modules.data?.modules.filter(module => module.module_id !== 'shell').map(module => <option key={module.module_id} value={module.module_id}>{module.title}</option>)}
    </select></label>
    {modules.error && <p role="alert">模块目录读取失败：{modules.error.message} <button type="button" onClick={() => void modules.refetch()}>重试</button></p>}
    {selected && loading && <p role="status">正在读取所选模块的本地已保存草稿…</p>}
    {selected && error && <p role="alert">草稿读取失败：{error.message} <button type="button" onClick={retry}>重试读取</button></p>}
    {selected && document && <small>将附带已保存版本 {document.revision}{document.sample_id ? ' · Mock 示例' : ''}；不包含编辑器未保存修改。</small>}
  </div>;
}
