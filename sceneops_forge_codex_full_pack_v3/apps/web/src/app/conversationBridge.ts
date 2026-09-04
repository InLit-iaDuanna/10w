import type { CommandRequest, WorkbenchCommandBusPort } from '@sceneops/conversation-home';
import type { CommandExecutionContext, WorkbenchCommandBus } from '@sceneops/forge-shell';

/** The assistant coordinator calls execute only after the user confirms its preview. */
export function conversationCommandBridge(bus: WorkbenchCommandBus, context: CommandExecutionContext): WorkbenchCommandBusPort {
  function command(request: CommandRequest) {
    if (request.commandId === 'workbench.command_search.open') return {
      id: 'workbench.open_editor', input: { editorId: 'shell.command-search', placement: { mode: 'drawer', edge: 'top' } },
    };
    return { id: request.commandId, input: request.input };
  }
  return {
    async inspect(request) {
      const { id, input } = command(request);
      const state = bus.availability(id, context, input);
      return {
        state: state.available ? 'available' : 'unavailable', layoutEffect: id === 'workbench.open_editor' ? 'material' : 'none',
        message: state.reason, missingPermissions: [], missingIntegrations: [], suggestedActions: [],
        approval: { required: false, state: 'not_required' },
      };
    },
    async preview(request) {
      const placement = request.input.placement as { mode?: string; direction?: string; edge?: string } | undefined;
      const labels: Record<string, string> = { right: '右侧', left: '左侧', above: '上方', below: '下方', top: '顶部', bottom: '底部' };
      const location = placement?.direction ?? placement?.edge ?? '';
      return { mode: 'planned', summary: '确认后打开工具，当前内容保留', changes: [`位置：${labels[location] ?? '当前区域'}${placement?.mode === 'split' ? '拆分' : ''}`], targetDescription: request.input.editorId === 'shell.tool-library' ? '工具库' : '命令搜索' };
    },
    async execute(request) {
      const { id, input } = command(request);
      // Explicit confirmation is a button action; assistant-supplied confirmed flags are never forwarded.
      const result = await bus.execute<any>(id, { ...context, source: 'button' }, input);
      if (['rejected', 'unavailable', 'confirmation-required'].includes(result?.status)) {
        throw new Error(`操作未执行：${result.reason ?? result.code ?? result.status}`);
      }
      return result;
    },
  };
}
