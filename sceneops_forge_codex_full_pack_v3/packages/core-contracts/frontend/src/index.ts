// Generated from Python Pydantic contracts. Do not edit.

export const CORE_CONTRACT_VERSION = 1 as const;

/** Stable identifier matching `^(?:usr|agt|svc|sys|prj|brn|scn|sobj|ast|aver|bld|run|iss|chg|apr|art|evt|cmd|corr|req|wfl|fea|tsk|rjob|prun)_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type StableId = string & { readonly __brand: "StableId" };

/** Stable identifier matching `^(?:usr|agt|svc|sys)_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type ActorId = string & { readonly __brand: "ActorId" };

/** Stable identifier matching `^usr_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type UserId = string & { readonly __brand: "UserId" };

/** Stable identifier matching `^agt_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type AgentId = string & { readonly __brand: "AgentId" };

/** Stable identifier matching `^svc_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type ServiceId = string & { readonly __brand: "ServiceId" };

/** Stable identifier matching `^sys_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type SystemActorId = string & { readonly __brand: "SystemActorId" };

/** Stable identifier matching `^prj_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type ProjectId = string & { readonly __brand: "ProjectId" };

/** Stable identifier matching `^brn_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type BranchId = string & { readonly __brand: "BranchId" };

/** Stable identifier matching `^scn_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type SceneId = string & { readonly __brand: "SceneId" };

/** Stable identifier matching `^sobj_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type SceneObjectId = string & { readonly __brand: "SceneObjectId" };

/** Stable identifier matching `^ast_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type AssetId = string & { readonly __brand: "AssetId" };

/** Stable identifier matching `^aver_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type AssetVersionId = string & { readonly __brand: "AssetVersionId" };

/** Stable identifier matching `^bld_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type BuildId = string & { readonly __brand: "BuildId" };

/** Stable identifier matching `^run_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type RunId = string & { readonly __brand: "RunId" };

/** Stable identifier matching `^iss_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type IssueId = string & { readonly __brand: "IssueId" };

/** Stable identifier matching `^chg_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type ChangeSetId = string & { readonly __brand: "ChangeSetId" };

/** Stable identifier matching `^apr_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type ApprovalId = string & { readonly __brand: "ApprovalId" };

/** Stable identifier matching `^art_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type ArtifactId = string & { readonly __brand: "ArtifactId" };

/** Stable identifier matching `^evt_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type EventId = string & { readonly __brand: "EventId" };

/** Stable identifier matching `^cmd_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type CommandId = string & { readonly __brand: "CommandId" };

/** Stable identifier matching `^corr_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type CorrelationId = string & { readonly __brand: "CorrelationId" };

/** Stable identifier matching `^req_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type RequestId = string & { readonly __brand: "RequestId" };

/** Stable identifier matching `^wfl_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type WorkflowId = string & { readonly __brand: "WorkflowId" };

/** Stable identifier matching `^fea_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type FeatureId = string & { readonly __brand: "FeatureId" };

/** Stable identifier matching `^tsk_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type TaskId = string & { readonly __brand: "TaskId" };

/** Stable identifier matching `^rjob_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type RenderJobId = string & { readonly __brand: "RenderJobId" };

/** Stable identifier matching `^prun_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$`. */
export type PlaytestRunId = string & { readonly __brand: "PlaytestRunId" };

/** Stable identifier matching `^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$`. */
export type ModuleId = string & { readonly __brand: "ModuleId" };

/** Stable identifier matching `^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$`. */
export type ContributionId = string & { readonly __brand: "ContributionId" };

/** Stable identifier matching `^sha256:[0-9a-f]{64}$`. */
export type Sha256Checksum = string & { readonly __brand: "Sha256Checksum" };

export interface ActorReference {
  "type": ActorType;
  "id": ActorId;
  "display_name"?: string | null;
}

export type ActorType = "user" | "agent" | "service" | "system";

export interface AiProvenance {
  "provider": string;
  "model": string;
  "workflow_hash": Sha256Checksum;
  "prompt": string;
  "negative_prompt"?: string | null;
  "seed"?: number | null;
  "parameters"?: Record<string, JsonValue>;
}

export interface ApprovalDecision {
  "approval_id": ApprovalId;
  "change_set_id": ChangeSetId;
  "decision": ApprovalDecisionValue;
  "actor": ActorReference;
  "decided_at": string;
  "comment"?: string | null;
}

export type ApprovalDecisionValue = "approved" | "rejected";

export interface ApprovalRequirement {
  "permission": string;
  "minimum_decisions"?: number;
  "allowed_actor_types"?: Array<ActorType>;
}

export type ApprovalState = "not_required" | "pending" | "approved" | "rejected";

export interface Artifact {
  "artifact_id": ArtifactId;
  "artifact_type": string;
  "version": string;
  "uri": string;
  "provenance": ArtifactProvenance;
  "metadata"?: Record<string, JsonValue>;
}

export interface ArtifactProvenance {
  "source_project_id": ProjectId;
  "source_version": string;
  "source_commit"?: string | null;
  "related_sceneops_ids"?: Array<SceneObjectId>;
  "producing_module": ModuleId;
  "tool_name": string;
  "tool_version": string;
  "adapter_version": string;
  "recipe_version": string;
  "creator": ActorReference;
  "execution_mode": ExecutionMode;
  "created_at": string;
  "checksum": Sha256Checksum;
  "approval_state": ApprovalState;
  "cached_from_run_id"?: RunId | null;
  "fixture_id"?: string | null;
  "ai"?: AiProvenance | null;
}

export interface ChangeSet {
  "change_set_id": ChangeSetId;
  "base_version": string;
  "target": ChangeSetTarget;
  "previous_values": Record<string, JsonValue>;
  "proposed_values": Record<string, JsonValue>;
  "rationale": string;
  "expected_result": string;
  "impact_scope": ImpactScope;
  "risk": RiskLevel;
  "validation_plan": Array<string>;
  "rollback_plan": Array<string>;
  "approval_requirements"?: Array<ApprovalRequirement>;
  "dry_run_supported"?: true;
  "destructive"?: boolean;
  "status"?: ChangeSetStatus;
  "created_by": ActorReference;
  "created_at": string;
}

export type ChangeSetStatus = "draft" | "waiting_approval" | "approved" | "rejected" | "executing" | "succeeded" | "failed" | "rolled_back";

export interface ChangeSetTarget {
  "module_id": ModuleId;
  "integration_id"?: ModuleId | null;
  "object_ids"?: Array<StableId>;
}

export interface CommandEnvelope {
  "command_id": CommandId;
  "command_type": ContributionId;
  "command_version"?: number;
  "issued_at": string;
  "project_id"?: ProjectId | null;
  "correlation_id": CorrelationId;
  "actor": ActorReference;
  "mode": ExecutionMode;
  "payload": JsonValue;
}

export interface EventEnvelope {
  "event_id": EventId;
  "event_type": ContributionId;
  "event_version": number;
  "occurred_at": string;
  "project_id"?: ProjectId | null;
  "correlation_id": CorrelationId;
  "causation_id"?: CommandId | null;
  "actor": ActorReference;
  "mode": ExecutionMode;
  "payload": JsonValue;
}

export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";

export type ImpactScope = "object" | "module" | "scene" | "project" | "repository" | "release";

export interface JobDefinition {
  "id": ContributionId;
  "module_id": ModuleId;
  "input_schema": string;
  "output_schema": string;
  "supports_dry_run"?: true;
  "cancellable": boolean;
  "retryable": boolean;
  "resumable": boolean;
}

export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface RunRecord {
  "run_id": RunId;
  "job_id": ContributionId;
  "state": RunState;
  "mode": ExecutionMode;
  "attempt"?: number;
  "created_at": string;
  "started_at"?: string | null;
  "finished_at"?: string | null;
  "error"?: StandardError | null;
  "artifact_ids"?: Array<ArtifactId>;
}

export type RunState = "queued" | "running" | "waiting_approval" | "succeeded" | "failed" | "cancelled" | "rolled_back";

export interface StandardError {
  "code": string;
  "message": string;
  "details"?: Record<string, JsonValue>;
  "request_id"?: RequestId | null;
  "retryable"?: boolean;
  "suggested_actions"?: Array<ContributionId>;
}

export type StandardErrorCode = "INVALID_ARGUMENT" | "NOT_FOUND" | "CONFLICT" | "PERMISSION_DENIED" | "PRECONDITION_FAILED" | "APPROVAL_REQUIRED" | "INTEGRATION_OFFLINE" | "TIMEOUT" | "CANCELLED" | "UNAVAILABLE" | "INTERNAL";

export interface WorkbenchContext {
  "project_id"?: ProjectId | null;
  "branch_id"?: BranchId | null;
  "scene_id"?: SceneId | null;
  "selected_scene_object_ids"?: Array<SceneObjectId>;
  "selected_asset_ids"?: Array<AssetId>;
  "active_feature_id"?: FeatureId | null;
  "active_task_id"?: TaskId | null;
  "active_change_set_id"?: ChangeSetId | null;
  "active_render_job_id"?: RenderJobId | null;
  "active_build_id"?: BuildId | null;
  "active_playtest_run_id"?: PlaytestRunId | null;
  "active_issue_id"?: IssueId | null;
  "camera_pose"?: Record<string, JsonValue> | null;
  "timeline_time"?: number | null;
}
