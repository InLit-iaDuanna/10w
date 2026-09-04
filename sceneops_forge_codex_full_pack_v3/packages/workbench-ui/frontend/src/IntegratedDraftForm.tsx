import { useCallback, useEffect, useState, type ReactNode } from 'react';
import type { IntegratedWorkbenchProps, JsonValue } from '@sceneops/core-ui';

export interface DraftField { key: string; label: string; multiline?: boolean; placeholder?: string }
export function useWorkbenchDraft(props: IntegratedWorkbenchProps) {
  const [payload, setPayload] = useState(props.document.payload);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const dirty = JSON.stringify(payload) !== JSON.stringify(props.document.payload);
  useEffect(() => { props.onDirtyChange(dirty); }, [dirty, props.onDirtyChange]);
  const update = useCallback((patch: Record<string, JsonValue>) => { setPayload(value => ({ ...value, ...patch })); setSaved(false); }, []);
  async function save() {
    setSaving(true); setError('');
    try { await props.onSave(payload); setSaved(true); props.onDirtyChange(false); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setSaving(false); }
  }
  return { payload, update, dirty, save, saving, saved, error };
}
export function IntegratedDraftForm({ title, fields, draft, children }: {
  title: string; fields: DraftField[]; draft: ReturnType<typeof useWorkbenchDraft>; children?: ReactNode;
}) {
  return <section className="integrated-draft" style={{ padding: 16 }}>
    <h3>{title} · 待执行草稿</h3>
    <p>只保存本地设计数据，不启动外部工具或案例。AI 建议由你手动采用。</p>
    <fieldset disabled={draft.saving} style={{ border: 0, display: 'grid', gap: 12, padding: 0 }}>
      {fields.map(field => <label key={field.key} style={{ display: 'grid', gap: 5 }}>{field.label}
        {field.multiline ? <textarea rows={3} value={String(draft.payload[field.key] ?? '')} placeholder={field.placeholder} onChange={event => draft.update({ [field.key]: event.target.value })}/>
          : <input value={String(draft.payload[field.key] ?? '')} placeholder={field.placeholder} onChange={event => draft.update({ [field.key]: event.target.value })}/>}
      </label>)}
      {children}
      <button type="button" onClick={() => void draft.save()}>{draft.saving ? '保存中…' : '保存本地草稿'}</button>
    </fieldset>
    {draft.error && <p role="alert">保存失败：{draft.error}。草稿仍保留，可重试。</p>}
    {draft.saved && <p role="status">已保存本地草稿。</p>}
    {draft.dirty && <p role="status">有未保存修改。</p>}
  </section>;
}
