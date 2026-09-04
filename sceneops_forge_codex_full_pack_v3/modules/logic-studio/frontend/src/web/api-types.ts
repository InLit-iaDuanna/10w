import type { components } from '../generated/workbench-api.ts';
export type GameplayGraph = components['schemas']['GameplayGraph'];
export type GameplayNode = components['schemas']['GameplayNode'];
export type GameplayEdge = components['schemas']['GameplayEdge'];
export type PreviewStep = components['schemas']['PreviewStep'];
export type PreviewResponse = components['schemas']['PreviewResponse'];
export type ChangeSet = components['schemas']['ChangeSet'];
export type CodeChangeSet = components['schemas']['CodeChangeSet'];
export type GraphProposalResponse = components['schemas']['GraphProposalResponse'];
export interface LogicWorkbenchApi {
  loadDemo: () => Promise<GameplayGraph>;
  validate: (graph: GameplayGraph) => Promise<components['schemas']['GraphValidationReport']>;
  preview: (request: components['schemas']['PreviewRequest']) => Promise<PreviewResponse>;
  propose: (request: components['schemas']['GraphProposalRequest']) => Promise<GraphProposalResponse>;
  proposeCode: (request: components['schemas']['CodeChangeProposal']) => Promise<CodeChangeSet>;
}
export const logicWorkbenchKeys = { demo: ['logic-studio', 'world-workbench', 'demo'] as const };
