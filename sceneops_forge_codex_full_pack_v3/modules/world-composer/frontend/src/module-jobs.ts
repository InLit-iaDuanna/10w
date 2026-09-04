import { validateLevel } from './level-gates.ts';

export const worldLevelValidationJob = {
  id: 'world.level.validate',
  retryPolicy: { maximumAttempts: 1 },
  cancellable: true,
  resumable: false,
  run: validateLevel,
};

export const worldWorkflows = [
  {
    id: 'asset-to-world-placement',
    steps: [
      'validate-drop',
      'create-changeset',
      'wait-for-approval',
      'adapter-dry-run',
      'adapter-execute',
      'world-level-validate',
    ],
  },
  {
    id: 'world-level-validation',
    steps: ['load-exact-scene-version', 'validate-input-freshness', 'run-six-level-gates'],
  },
] as const;

export const worldLevelPolicyGate = {
  id: 'world.level',
  evaluate: validateLevel,
};
