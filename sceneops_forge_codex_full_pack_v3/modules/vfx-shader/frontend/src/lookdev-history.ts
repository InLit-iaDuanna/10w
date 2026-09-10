import { applyOperations, parseProject, validateOperations, type LookdevProject, type EditScope } from './core/lookdev';
export interface LookdevHistory { past: LookdevProject[]; present: LookdevProject; future: LookdevProject[] }
export function editLookdev(history: LookdevHistory, operations: unknown, source: 'manual' | 'ai', summary: string, scope?: EditScope): LookdevHistory {
  const validated = validateOperations(history.present, operations, scope);
  const present = parseProject(applyOperations(history.present, validated, source, summary));
  return { past: [...history.past, history.present], present, future: [] };
}
export function moveLookdevHistory(history: LookdevHistory, direction: 'undo' | 'redo'): LookdevHistory {
  if (direction === 'undo') {
    if (!history.past.length) return history;
    return { past: history.past.slice(0, -1), present: history.past.at(-1)!, future: [history.present, ...history.future] };
  }
  if (!history.future.length) return history;
  return { past: [...history.past, history.present], present: history.future[0], future: history.future.slice(1) };
}

/** Document history stores snapshots, while the project itself owns its edit log. */
export function storeLookdevHistory(history: LookdevHistory): Record<string, unknown>[] {
  return [{ kind: 'lookdev.history@1', past: history.past, future: history.future }];
}
export function restoreLookdevHistory(project: LookdevProject, records: Record<string, unknown>[] = []): LookdevHistory {
  const timeline = records.find(record => record.kind === 'lookdev.history@1');
  if (!timeline) return {past:[],present:project,future:[]};
  if (!Array.isArray(timeline.past) || !Array.isArray(timeline.future)) throw new Error('工程历史格式无效。');
  const bindings = (value: LookdevProject) => JSON.stringify([value.source,value.objects.map(object=>[object.id,object.materialSlots.map(slot=>[slot.slot,slot.sourceMaterialId])])]);
  const expected = bindings(project);
  const read = (value: unknown) => {const parsed=parseProject(value);if(bindings(parsed)!==expected)throw new Error('工程历史与资产绑定不一致。');return parsed;};
  return {present:project,past:timeline.past.map(read),future:timeline.future.map(read)};
}
