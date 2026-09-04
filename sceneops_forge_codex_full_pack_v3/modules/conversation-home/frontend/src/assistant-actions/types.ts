import type { JsonObject } from "../contracts/json.ts";

export interface AssistantContextReference {
  projectId?: string;
  sceneId?: string;
  sceneObjectIds?: string[];
  featureId?: string;
  buildId?: string;
  issueId?: string;
}

export type EditorPlacement =
  | {
      mode: "replace" | "tab";
      relativeToInstanceId?: string;
    }
  | {
      mode: "split";
      direction: "left" | "right" | "above" | "below";
      relativeToInstanceId?: string;
    }
  | { mode: "floating" | "popout" }
  | {
      mode: "drawer";
      edge: "left" | "right" | "top" | "bottom";
    };

interface AssistantActionBase<TType extends string, TInput> {
  actionId: string;
  type: TType;
  title: string;
  input: TInput;
}

export type OpenEditorAction = AssistantActionBase<
  "workbench.open_editor",
  {
    editorId: string;
    placement: EditorPlacement;
    context?: AssistantContextReference;
  }
> & {
  requiresConfirmation: true;
};

export type CreateProjectAction = AssistantActionBase<
  "project.create",
  {
    changeSetId: string;
    name: string;
    brief?: string;
    sourceAttachmentId?: string;
  }
>;

export type CreateFeatureAction = AssistantActionBase<
  "feature.create",
  {
    changeSetId: string;
    projectId: string;
    title: string;
    brief: string;
  }
>;

export type RunWorkflowAction = AssistantActionBase<
  "workflow.run",
  {
    changeSetId: string;
    projectId: string;
    workflowId: string;
    parameters: JsonObject;
  }
>;

export type OpenArtifactAction = AssistantActionBase<
  "artifact.open",
  {
    artifactId: string;
    preferredEditorId?: string;
  }
>;

export type OpenIssueAction = AssistantActionBase<
  "issue.open_backpin",
  { issueId: string }
>;

export type RequestApprovalAction = AssistantActionBase<
  "changeset.approval.request",
  {
    changeSetId: string;
    reason?: string;
  }
>;

export type AssistantAction =
  | OpenEditorAction
  | CreateProjectAction
  | CreateFeatureAction
  | RunWorkflowAction
  | OpenArtifactAction
  | OpenIssueAction
  | RequestApprovalAction;

export type AssistantActionType = AssistantAction["type"];

export const assistantActionTypes = [
  "workbench.open_editor",
  "project.create",
  "feature.create",
  "workflow.run",
  "artifact.open",
  "issue.open_backpin",
  "changeset.approval.request",
] as const satisfies readonly AssistantActionType[];
