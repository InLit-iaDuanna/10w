import { describe, expect, it, vi } from 'vitest';
import {
  captureAnimationPreviewCommand,
  executeUnityMappingCommand,
  inspectCharacterCommand,
} from '../commands';
import { rememberHomeCharacterBundle } from '../fixtures/rememberHome';
import type { CommandGuardContext, WorkbenchContext } from '../types';

const workbench: WorkbenchContext = {
  projectId: 'prj_remember_home',
  selectedAssetIds: [],
  activeFeatureId: 'feature_key_door_branch',
  activeTaskId: 'task_player_traversal',
  activeChangeSetId: null,
};

function guard(overrides: Partial<CommandGuardContext> = {}): CommandGuardContext {
  return {
    workbench,
    moduleEnabled: true,
    permissions: new Set(['character:read', 'animation:read', 'character:write', 'character:review', 'unity:write']),
    integrations: new Set(['character-preview', 'retargeting', 'unity']),
    ...overrides,
  };
}

describe('typed command handlers', () => {
  it('uses the host API port rather than a component-local network path', async () => {
    const expected = { bundle: rememberHomeCharacterBundle, report: { automated_outcome: 'passed' } };
    const post = vi.fn().mockResolvedValue(expected);
    const input = {
      request_id: 'req_frontend_inspect',
      bundle: rememberHomeCharacterBundle,
      mode: 'mock' as const,
    };
    expect(inspectCharacterCommand.inputSchema.parse(input)).toEqual(input);
    await expect(inspectCharacterCommand.execute({ api: { post }, workbench }, input)).resolves.toBe(expected);
    expect(post).toHaveBeenCalledWith('/api/modules/character-animation/inspect', input);
  });

  it('makes disabled, permission, missing-project, and offline states explicit', () => {
    expect(inspectCharacterCommand.canExecute(guard({ moduleEnabled: false })).code).toBe('MODULE_DISABLED');
    expect(inspectCharacterCommand.canExecute(guard({ permissions: new Set() })).code).toBe('PERMISSION_DENIED');
    expect(
      inspectCharacterCommand.canExecute(guard({ workbench: { ...workbench, projectId: null } })).code,
    ).toBe('PROJECT_REQUIRED');
    expect(captureAnimationPreviewCommand.canExecute(guard({ integrations: new Set() })).code).toBe(
      'INTEGRATION_OFFLINE',
    );
    expect(executeUnityMappingCommand.canExecute(guard({ integrations: new Set() })).reason).toContain('unity');
  });
});
