import type { AudioCommand, AudioCommandGateway, AudioCommandInput, CommandAvailability, RuntimeInputSchema } from './types';

function inputRecord(input: unknown): AudioCommandInput {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('AUDIO_COMMAND_INPUT_INVALID: 命令输入必须是对象。');
  return input as AudioCommandInput;
}

function text(input: AudioCommandInput, field: string): string {
  const value = input[field];
  if (typeof value !== 'string' || !value.trim()) throw new Error(`AUDIO_COMMAND_INPUT_INVALID: 缺少有效字段 ${field}。`);
  return value;
}

function rejectUnknown(input: AudioCommandInput, fields: readonly string[]): void {
  for (const key of Object.keys(input)) if (!fields.includes(key)) throw new Error(`AUDIO_COMMAND_INPUT_INVALID: 未知字段 ${key}。`);
}

export const audioCommandSchemas: Record<string, RuntimeInputSchema> = {
  createSpec: { parse(value) {
    const input = inputRecord(value); const fields = ['specId', 'projectId', 'purpose', 'intendedEvents', 'mixerGroup', 'generationReference'];
    rejectUnknown(input, fields);
    const events = input.intendedEvents;
    if (!Array.isArray(events) || !events.length || events.some(event => typeof event !== 'string' || !event.startsWith('gameplay.'))) throw new Error('AUDIO_COMMAND_INPUT_INVALID: intendedEvents 必须是 gameplay 事件数组。');
    const generationReference = input.generationReference;
    if (generationReference !== undefined && (typeof generationReference !== 'string' || !generationReference.trim())) throw new Error('AUDIO_COMMAND_INPUT_INVALID: generationReference 必须是非空字符串。');
    return { specId: text(input, 'specId'), projectId: text(input, 'projectId'), purpose: text(input, 'purpose'), intendedEvents: events, mixerGroup: text(input, 'mixerGroup'), ...(generationReference ? { generationReference } : {}) };
  } },
  inspectAsset: { parse(value) {
    const input = inputRecord(value); rejectUnknown(input, ['assetId', 'filename', 'uploadId']);
    return { assetId: text(input, 'assetId'), filename: text(input, 'filename'), uploadId: text(input, 'uploadId') };
  } },
  bindEvent: { parse(value) {
    const input = inputRecord(value); rejectUnknown(input, ['gameplayEvent', 'audioAssetId']);
    const gameplayEvent = text(input, 'gameplayEvent');
    if (!gameplayEvent.startsWith('gameplay.')) throw new Error('AUDIO_COMMAND_INPUT_INVALID: gameplayEvent 命名空间无效。');
    return { gameplayEvent, audioAssetId: text(input, 'audioAssetId') };
  } },
  mapAudio: { parse(value) {
    const input = inputRecord(value);
    rejectUnknown(input, ['mappingId', 'changeSetId', 'audioAssetId', 'targetSceneopsId', 'audioSourceName', 'mixerGroup']);
    const targetSceneopsId = text(input, 'targetSceneopsId');
    if (!targetSceneopsId.startsWith('so_')) throw new Error('AUDIO_COMMAND_INPUT_INVALID: targetSceneopsId 必须使用 so_ ID。');
    return { mappingId: text(input, 'mappingId'), changeSetId: text(input, 'changeSetId'), audioAssetId: text(input, 'audioAssetId'), targetSceneopsId, audioSourceName: text(input, 'audioSourceName'), mixerGroup: text(input, 'mixerGroup') };
  } },
};

const enabled = ({ moduleEnabled }: { moduleEnabled: boolean }): CommandAvailability =>
  moduleEnabled ? { available: true } : { available: false, reason: '音频工作室已禁用。' };
const publishing = ({ moduleEnabled, unityOnline }: { moduleEnabled: boolean; unityOnline: boolean }): CommandAvailability =>
  !moduleEnabled ? { available: false, reason: '音频工作室已禁用。' } : unityOnline ? { available: true } : { available: false, reason: 'Unity 未连接；映射将保留为提案。' };

function command(id: string, title: string, requiredPermissions: string[], schema: RuntimeInputSchema,
                 canExecute: AudioCommand['canExecute']): AudioCommand {
  return {
    id, title, requiredPermissions, inputSchema: schema, canExecute,
    async execute(gateway: AudioCommandGateway, input: unknown, availability): Promise<unknown> {
      const state = canExecute(availability);
      if (!state.available) throw new Error(`AUDIO_COMMAND_UNAVAILABLE: ${state.reason}`);
      return gateway.execute(id, schema.parse(input));
    },
  };
}

export const audioCommands: AudioCommand[] = [
  command('audio.spec.create', '创建音频任务', ['audio:write'], audioCommandSchemas.createSpec, enabled),
  command('audio.asset.inspect', '分析音频文件', ['audio:read'], audioCommandSchemas.inspectAsset, enabled),
  command('audio.event.bind', '绑定游戏事件', ['audio:write'], audioCommandSchemas.bindEvent, enabled),
  command('audio.mapping.propose', '提出 Unity 音频映射', ['audio:write'], audioCommandSchemas.mapAudio, publishing),
  command('audio.mapping.publish', '发布已批准映射', ['audio:publish'], audioCommandSchemas.mapAudio, publishing),
];

/** Replace these structural local types with core public command types once the core runtime is available. */
