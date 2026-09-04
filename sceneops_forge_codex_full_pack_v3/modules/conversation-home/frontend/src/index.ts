import type { ModuleContribution } from "@sceneops/module-runtime";
import { assistantConversationEditor } from "./editorDefinition.ts";
import { manifest } from "./manifest.ts";

export const moduleContribution = {
  manifest,
  editors: [assistantConversationEditor],
} satisfies ModuleContribution;

export { AssistantActionCoordinator } from "./assistant-actions/coordinator.ts";
export { validateAssistantAction } from "./assistant-actions/validate.ts";
export { assistantActionTypes } from "./assistant-actions/types.ts";
export type {
  AssistantAction,
  AssistantActionType,
  AssistantContextReference,
  CreateFeatureAction,
  CreateProjectAction,
  EditorPlacement,
  OpenEditorAction,
  OpenArtifactAction,
  OpenIssueAction,
  RequestApprovalAction,
  RunWorkflowAction,
} from "./assistant-actions/types.ts";
export type {
  ActionExecutionResult,
  ActionOrigin,
  CommandAvailability,
  CommandRequest,
  LayoutActionPreview,
  PreparedAction,
  WorkbenchCommandBusPort,
  WorkbenchContextSnapshot,
} from "./assistant-actions/coordinator.ts";
export type {
  ActionValidationIssue,
  ActionValidationResult,
} from "./assistant-actions/validate.ts";
export { ConversationController } from "./conversation/controller.ts";
export {
  ConversationRepository,
  createConversationRecord,
  isConversationRecord,
} from "./conversation/repository.ts";
export type {
  ConversationInitializeResult,
  ConversationOperationResult,
  IdFactory,
  UtcClock,
} from "./conversation/controller.ts";
export type {
  ConversationLoadResult,
  ConversationSaveResult,
  ConversationStorageFailure,
  KeyValueStorage,
} from "./conversation/repository.ts";
export {
  createConversationEditorRuntime,
  WorkbenchCommandUnavailableError,
} from "./editors/createRuntime.ts";
export type { ConversationRuntimeDependencies } from "./editors/createRuntime.ts";
export {
  blockedConversationAvailability,
  type ConversationAvailability,
  type ConversationEditorRuntime,
} from "./editors/runtime.ts";
export {
  ConversationTransportError,
  isConversationTransportError,
} from "./conversation/transport.ts";
export type {
  ConversationRequest,
  ConversationRun,
  ConversationStreamEvent,
  ConversationTransport,
  ConversationTransportFailureShape,
} from "./conversation/transport.ts";
export { toConversationAttachment } from "./composer/attachments.ts";
export type {
  BrowserAttachmentSource,
  BrowserDirectoryEntryHandle,
  BrowserDirectoryEntryReader,
  BrowserFileEntryHandle,
  BrowserFileSystemEntryHandle,
  ConversationAttachmentStager,
  DroppedEntryMetadata,
} from "./composer/attachments.ts";
export type {
  ApprovalCard,
  ArtifactCard,
  ArtifactProvenanceSummary,
  AssistantActionCard,
  ConversationCard,
  ErrorCard,
  OpenInToolCard,
  ProgressCard,
  ProgressNode,
  ProgressNodeState,
  SuggestedCommand,
} from "./conversation/cards.ts";
export type {
  ExecutionMode,
  ExecutionModePresentation,
} from "./contracts/executionMode.ts";
export type { JsonObject, JsonValue } from "./contracts/json.ts";
export type {
  ConversationAttachment,
  ConversationMessage,
  ConversationMessageStatus,
  ConversationRecord,
  ConversationScope,
  WorkbenchContextSummary,
} from "./conversation/types.ts";
export {
  chatOnlyHomeFixture,
  selectHomeStartup,
} from "./fixtures/chatOnlyHome.ts";
export type {
  ChatOnlyHomeFixture,
  HomeStartupDecision,
  StartupContext,
} from "./fixtures/chatOnlyHome.ts";

export { assistantConversationEditor } from "./editorDefinition.ts";
export { LocalConversationTransport } from './fixtures/LocalConversationTransport.ts';
export { CodeBuddyConversationTransport, getCodeBuddyModels } from './conversation/CodeBuddyConversationTransport.ts';
export type { CodeBuddyModel, CodeBuddyModelCatalog } from './conversation/CodeBuddyConversationTransport.ts';
export { UnifiedConversation } from './unified/UnifiedConversation.tsx';
export { AIAdvicePanel } from './unified/AIAdvicePanel.tsx';
export { aiKeys } from './unified/aiClient.ts';
