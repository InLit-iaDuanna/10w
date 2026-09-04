import { worldCommandDefinitions } from './commands.ts';
import { worldEditorDefinitions } from './editors/definitions.ts';
import { worldLevelPolicyGate, worldLevelValidationJob, worldWorkflows } from './module-jobs.ts';

export const manifest = {
  schemaVersion: 1,
  id: 'world-composer',
  version: '0.1.0',
  featureFlag: 'world_composer',
} as const;

export const moduleContribution = {
  manifest,
  editors: worldEditorDefinitions,
  commands: worldCommandDefinitions,
  events: [
    'scene.annotation.created@1',
    'scene.object.placement_proposed@1',
    'scene.level.validated@1',
  ],
  jobs: [worldLevelValidationJob],
  workflows: worldWorkflows,
  policyGates: [worldLevelPolicyGate],
};
