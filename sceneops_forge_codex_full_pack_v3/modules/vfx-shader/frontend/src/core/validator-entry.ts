/** Fixed JSON-only validator bridge. No dynamic imports, supplied code, commands or paths. */
import { z } from 'zod/v4';
import { parseProject, validateOperations, applyOperations, operationSchema, editResponseSchema } from './lookdev';
import { generateTslMaterialModule, encodeShaderPackage } from './shader-package';
import { encodeProject } from './project-package';
import JSZip from 'jszip';

import { generateGameModule } from './game-module';

import { proposalPrompt, expandShaderGraphOperations } from './ai-proposal';
const scopeSchema = z.object({ materialIds: z.array(z.string()), lightIds: z.array(z.string()), lighting: z.boolean() }).strict();
const project = z.unknown();
const request = z.discriminatedUnion('action', [
  z.object({ action: z.literal('validate'), project }).strict(),
  z.object({ action: z.literal('export'), project, format: z.enum(['luma-zip','shader-zip']), sourceBase64: z.string().optional(), history: z.object({past:z.array(z.unknown()),future:z.array(z.unknown())}).strict().optional() }).strict(),
  z.object({ action: z.literal('generate-game'), project }).strict(),
  z.object({ action: z.literal('schema') }).strict(),
  z.object({ action: z.literal('proposal-context'), project, scope: scopeSchema, selectedObjectId: z.string().optional(), selectedMaterialId: z.string().optional() }).strict(),
  z.object({ action: z.literal('apply'), project, operations: z.unknown(),
    scope: z.object({ materialIds: z.array(z.string()), lightIds: z.array(z.string()), lighting: z.boolean() }).strict().optional(),
    source: z.enum(['manual', 'ai']), summary: z.string().min(1).max(4000) }).strict(),
  z.object({ action: z.literal('generate'), project, materialId: z.string().min(1) }).strict(),
]);

async function main() {
  let input = '';
  for await (const chunk of process.stdin) {
    input += chunk;
    if (Buffer.byteLength(input) > 160 * 1024 * 1024) throw new Error('Lookdev validation input exceeds 160 MiB.');
  }
  const parsed = request.parse(JSON.parse(input));
  if (parsed.action !== 'export' && Buffer.byteLength(input) > 16 * 1024 * 1024) throw new Error('Lookdev validation input exceeds 16 MiB.');
  if (parsed.action === 'schema') return { valid: true, schema: z.toJSONSchema(z.array(operationSchema).min(1).max(16)) };
  const normalized = parseProject(parsed.project);
  if (parsed.action === 'export') {
    if (parsed.format === 'luma-zip') {
      const bytes = parsed.sourceBase64 ? Uint8Array.from(Buffer.from(parsed.sourceBase64, 'base64')) : null;
      const history = {past:(parsed.history?.past ?? []).map(parseProject),future:(parsed.history?.future ?? []).map(parseProject)};
      return {valid:true,base64:Buffer.from(await encodeProject({project:normalized,history,source:bytes?.buffer ?? null})).toString('base64')};
    }
    const zip = new JSZip();
    zip.file('sceneops-lookdev.ts', generateGameModule(normalized));
    zip.file('project.json', JSON.stringify(normalized, null, 2));
    for (const [index, material] of normalized.materials.entries()) {
      if (material.shaderGraph) zip.file(`materials/${index}.zip`, await encodeShaderPackage(material));
    }
    zip.file('README.md', 'Three.js 0.185.1 / WebGPU。sceneops-lookdev.ts 包含图与程序化效果；纹理来自原始 GLB。');
    return {valid:true,base64:await zip.generateAsync({type:'base64',compression:'DEFLATE'})};
  }
  if (parsed.action === 'proposal-context') return { valid: true, prompt: proposalPrompt(normalized, parsed.scope, parsed.selectedObjectId, parsed.selectedMaterialId), schema: z.toJSONSchema(z.object({ status: z.enum(['applied', 'declined', 'noop']), summary: z.string().min(1), operations: z.array(operationSchema).max(16) }).strict()) };
  if (parsed.action === 'generate-game') return { valid: true, code: generateGameModule(normalized) };
  if (parsed.action === 'validate') return { valid: true, project: normalized };
  if (parsed.action === 'generate') {
    const material = normalized.materials.find(item => item.id === parsed.materialId);
    if (!material) throw new Error('Material does not exist.');
    return { valid: true, code: generateTslMaterialModule(material) };
  }
  if (parsed.source === 'ai' && !parsed.scope) throw new Error('AI operations require explicit edit scope.');
  const operations = validateOperations(normalized, (expandShaderGraphOperations({ operations: parsed.operations }) as { operations: unknown }).operations, parsed.scope);
  return { valid: true, operations, project: parseProject(applyOperations(normalized, operations, parsed.source, parsed.summary)) };
}
main().then(result => process.stdout.write(JSON.stringify(result))).catch(error => {
  process.stdout.write(JSON.stringify({ valid: false, error: error instanceof Error ? error.message : String(error) }));
  process.exitCode = 1;
});
