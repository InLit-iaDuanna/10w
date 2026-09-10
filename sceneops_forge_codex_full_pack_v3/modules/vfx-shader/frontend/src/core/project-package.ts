import JSZip from 'jszip';
import { z } from 'zod/v4';
import { parseProject, projectSchema, type LookdevProject } from './lookdev';

export type ProjectHistory = { past: LookdevProject[]; future: LookdevProject[] };
export type ProjectPackage = {
  project: LookdevProject; history: ProjectHistory; source: ArrayBuffer | null;
};
const manifest = z.object({
  format: z.literal('lumaform'), version: z.literal(1), project: projectSchema,
  history: z.object({ past: z.array(projectSchema), future: z.array(projectSchema) }).strict(),
}).strict();
const storedState = projectSchema.omit({ editLog: true }).extend({ editLogHead: z.string().nullable() });
const compactManifest = z.object({
  format: z.literal('lumaform'), version: z.union([z.literal(2), z.literal(3)]), project: storedState,
  history: z.object({ past: z.array(storedState), future: z.array(storedState) }).strict(),
  events: z.array(z.object({ entry: projectSchema.shape.editLog.element, parent: z.string().nullable() }).strict()),
}).strict();

function validateHistory(project: LookdevProject, history: ProjectHistory) {
  const bindings = (p: LookdevProject) => JSON.stringify([p.source, p.objects.map(o => [o.id, o.materialSlots.map(s => [s.slot, s.sourceMaterialId])])]);
  const expected = bindings(project);
  for (const state of [...history.past, ...history.future]) {
    parseProject(state);
    if (bindings(state) !== expected) throw new Error('工程历史与当前模型不匹配。');
  }
}

export async function encodeProject(bundle: ProjectPackage): Promise<Uint8Array> {
  const project = parseProject(bundle.project);
  validateHistory(project, bundle.history);
  if (project.source.kind === 'glb' && !bundle.source) throw new Error('原始 GLB 缺失，无法保存完整工程。');
  const zip = new JSZip();
  const events = new Map<string, { entry: LookdevProject['editLog'][number]; parent: string | null }>();
  function store(state: LookdevProject) {
    const { editLog, ...data } = state;
    let parent: string | null = null;
    for (const entry of editLog) {
      const previous = events.get(entry.id);
      if (previous && (previous.parent !== parent || JSON.stringify(previous.entry) !== JSON.stringify(entry))) throw new Error('编辑记录 ID 或顺序冲突。');
      events.set(entry.id, { entry, parent }); parent = entry.id;
    }
    return { ...data, editLogHead: parent };
  }
  const packed = { format: 'lumaform', version: 3, project: store(project), history: { past: bundle.history.past.map(store), future: bundle.history.future.map(store) }, events: [...events.values()] };
  zip.file('project.json', JSON.stringify(packed));
  if (bundle.source) zip.file('assets/source.glb', bundle.source);
  return zip.generateAsync({ type: 'uint8array', compression: 'DEFLATE', compressionOptions: { level: 3 } });
}

export async function decodeProject(bytes: ArrayBuffer): Promise<ProjectPackage> {
  const zip = await JSZip.loadAsync(bytes);
  const entry = zip.file('project.json');
  if (!entry) throw new Error('工程包缺少 project.json。');
  const raw = JSON.parse(await entry.async('string'));
  let parsed: z.infer<typeof manifest>;
  if (raw.version === 2 || raw.version === 3) {
    const compact = compactManifest.parse(raw);
    const events = new Map(compact.events.map(event => [event.entry.id, event]));
    if (events.size !== compact.events.length) throw new Error('编辑记录 ID 重复。');
    function restore(state: z.infer<typeof storedState>): LookdevProject {
      const { editLogHead, ...data } = state;
      const editLog: LookdevProject['editLog'] = [];
      const seen = new Set<string>();
      let id = editLogHead;
      while (id !== null) {
        if (seen.has(id)) throw new Error('编辑记录存在循环。');
        seen.add(id);
        const event = events.get(id);
        if (!event) throw new Error('编辑记录引用缺失。');
        editLog.push(event.entry); id = event.parent;
      }
      return { ...data, editLog: editLog.reverse() };
    }
    parsed = { format: 'lumaform', version: 1, project: restore(compact.project), history: { past: compact.history.past.map(restore), future: compact.history.future.map(restore) } };
  } else parsed = manifest.parse(raw);
  const project = parseProject(parsed.project);
  parsed.history.past.forEach(parseProject); parsed.history.future.forEach(parseProject);
  validateHistory(project, parsed.history);
  const source = project.source.kind === 'glb' ? await zip.file('assets/source.glb')?.async('arraybuffer') : null;
  if (project.source.kind === 'glb' && !source) throw new Error('工程包缺少原始 GLB。');
  return { project, source: source ?? null, history: parsed.history };
}

export function downloadBlob(data: BlobPart, fileName: string, type: string) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const link = document.createElement('a');
  link.href = url; link.download = fileName; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
