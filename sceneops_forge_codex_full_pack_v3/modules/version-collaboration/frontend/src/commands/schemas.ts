import { z, type ZodType } from "zod";

import type {
  AcquireLockRequest,
  AddCommentRequest,
  AssignmentRequest,
  CreateReviewCommand,
  DecisionRequest,
  ExecuteRollbackRequest,
  ObserveApprovalRequest,
  ProposeRollbackRequest,
  ReleaseLinkRequest,
  ReleaseLockRequest,
} from "../generated/api-types.ts";

const stableId = z.string().min(3).max(160).regex(/^[A-Za-z][A-Za-z0-9_.:-]*$/);
const commitId = z.string().regex(/^[0-9a-fA-F]{7,64}$/);
const executionMode = z.enum(["live", "cached", "mock", "planned", "blocked"]);
const relativePath = z.string().min(1).max(4096).refine((value) => {
  const normalized = value.replaceAll("\\", "/");
  return !normalized.startsWith("/")
    && !normalized.startsWith("./")
    && !normalized.split("/").includes("..");
}, "path must stay inside the project");
const jsonRecord = z.record(z.string(), z.unknown());

const versionReference = z.object({
  provider: z.literal("git").default("git"),
  repository_id: stableId,
  object_format: z.enum(["sha1", "sha256"]).default("sha1"),
  commit_id: commitId,
  branch: z.string().min(1).max(255).nullable().optional(),
}).strict().superRefine((value, context) => {
  const expected = value.object_format === "sha1" ? 40 : 64;
  if (value.commit_id.length !== expected) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["commit_id"],
      message: `${value.object_format} requires a full ${expected}-character object ID`,
    });
  }
  if (
    value.branch != null
    && (value.branch.startsWith("-") || value.branch.includes("..") || value.branch.endsWith("/"))
  ) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["branch"],
      message: "branch is not a safe Git reference name",
    });
  }
});

const semanticEntity = z.object({
  entity_id: stableId,
  entity_kind: z.string().min(1).max(120),
  schema_id: z.string().min(1).max(200),
  schema_version: z.number().int().min(1),
  artifact_id: stableId,
  producer_module: z.string().min(1).max(120),
  values: jsonRecord,
  mode: executionMode,
}).strict();

const cameraPose = z.object({
  coordinate_space: z.literal("world").default("world"),
  axis_convention: z.literal("right-handed-y-up").default("right-handed-y-up"),
  position_m: z.tuple([z.number(), z.number(), z.number()]),
  rotation_xyzw: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  projection: z.enum(["perspective", "orthographic"]),
  vertical_fov_degrees: z.number().gt(0).lt(180).nullable().optional(),
}).strict();

const visualCapture = z.object({
  artifact_id: stableId,
  camera_id: stableId,
  pose: cameraPose,
  width: z.number().int().gt(0).max(16384),
  height: z.number().int().gt(0).max(16384),
  channels: z.number().int().min(1).max(4).default(1),
  color_space: z.string().min(1).max(80),
  capture_recipe_version: z.string().min(1).max(80),
  renderer_version: z.string().min(1).max(160),
  pixels: z.array(z.number().int().min(0).max(255)),
  mode: executionMode,
}).strict().superRefine((value, context) => {
  if (value.pixels.length !== value.width * value.height * value.channels) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["pixels"],
      message: "pixel sample count does not match dimensions and channels",
    });
  }
});

const behaviorAssertion = z.object({
  assertion_id: stableId,
  passed: z.boolean(),
  observed: z.unknown().optional(),
  expected: z.unknown().optional(),
}).strict();

const behaviorStep = z.object({
  step_id: stableId,
  action_id: stableId,
  outcome: z.string().min(1).max(500),
  goal_progress: z.number().min(0).max(1),
  target_sceneops_id: stableId.nullable().optional(),
}).strict();

const behaviorSnapshot = z.object({
  run_id: stableId,
  test_case_id: stableId,
  build_id: stableId,
  protocol_version: z.string().min(1).max(80),
  config_id: stableId,
  start_state_id: stableId,
  seed: z.number().int(),
  objective_succeeded: z.boolean(),
  assertions: z.array(behaviorAssertion),
  steps: z.array(behaviorStep),
  mode: executionMode,
}).strict();

const commentAnchor = z.object({
  kind: z.enum(["asset", "scene_object", "code_range", "render", "build", "playtest_step", "issue"]),
  review_revision_id: stableId,
  diff_bundle_id: stableId,
  version: versionReference,
  target_id: stableId,
  file_path: relativePath.nullable().optional(),
  start_line: z.number().int().min(1).nullable().optional(),
  end_line: z.number().int().min(1).nullable().optional(),
}).strict().superRefine((value, context) => {
  const hasRange = value.file_path != null || value.start_line != null || value.end_line != null;
  if (value.kind === "code_range") {
    if (value.file_path == null || value.start_line == null || value.end_line == null) {
      context.addIssue({ code: z.ZodIssueCode.custom, message: "code range anchor is incomplete" });
    } else if (value.end_line < value.start_line) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["end_line"], message: "end_line precedes start_line" });
    }
  } else if (hasRange) {
    context.addIssue({ code: z.ZodIssueCode.custom, message: "only code range anchors accept file and line fields" });
  }
});

export const createReviewSchema = z.object({
  review_id: stableId.nullable().optional(),
  expected_previous_revision_id: stableId.nullable().optional(),
  project_id: stableId,
  repository_id: stableId,
  title: z.string().min(1).max(240),
  base_commit: commitId,
  target_commit: commitId,
  semantic_before: z.array(semanticEntity).nullable().optional(),
  semantic_after: z.array(semanticEntity).nullable().optional(),
  visual_before: visualCapture.nullable().optional(),
  visual_after: visualCapture.nullable().optional(),
  behavior_before: behaviorSnapshot.nullable().optional(),
  behavior_after: behaviorSnapshot.nullable().optional(),
  target_ids: z.array(stableId).optional(),
  evidence_ids: z.array(stableId).optional(),
}).strict().superRefine((value, context) => {
  const hasReview = value.review_id != null;
  const hasPrevious = value.expected_previous_revision_id != null;
  if (hasReview !== hasPrevious) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "review_id and expected_previous_revision_id must be supplied together",
    });
  }
}) as unknown as ZodType<CreateReviewCommand>;

export const addCommentSchema = z.object({
  body: z.string().min(1).max(20_000),
  anchor: commentAnchor,
}).strict() as unknown as ZodType<AddCommentRequest>;

export const assignmentSchema = z.object({
  reviewer_id: stableId,
  action: z.enum(["assigned", "unassigned"]),
}).strict() as unknown as ZodType<AssignmentRequest>;

export const decisionSchema = z.object({
  outcome: z.enum(["accept", "request_changes", "block"]),
  rationale: z.string().min(1).max(10_000),
  evidence_ids: z.array(stableId).optional(),
}).strict() as unknown as ZodType<DecisionRequest>;

export const observeApprovalSchema = z.object({
  approval_id: stableId,
  subject_kind: z.enum(["review", "changeset", "rollback"]),
  subject_id: stableId,
  subject_version: z.number().int().min(1),
  current_base: versionReference,
}).strict() as unknown as ZodType<ObserveApprovalRequest>;

export const acquireLockSchema = z.object({
  review_id: stableId,
  project_id: stableId,
  repository_id: stableId,
  resource_id: stableId,
  path: relativePath,
}).strict() as unknown as ZodType<AcquireLockRequest>;

export const releaseLockSchema = z.object({
  review_id: stableId,
  project_id: stableId,
  resource_id: stableId,
}).strict() as unknown as ZodType<ReleaseLockRequest>;

export const proposeRollbackSchema = z.object({
  review_id: stableId,
  target_commit: commitId,
  current_base: versionReference,
  rationale: z.string().min(1).max(10_000),
}).strict() as unknown as ZodType<ProposeRollbackRequest>;

export const executeRollbackSchema = z.object({
  proposal_id: stableId,
  approval_id: stableId,
  current_base: versionReference,
}).strict() as unknown as ZodType<ExecuteRollbackRequest>;

export const releaseLinkSchema = z.object({
  review_id: stableId,
  approval_id: stableId,
  approved_subject_id: stableId,
  approved_subject_version: z.number().int().min(1),
  release_id: stableId,
  evidence_ids: z.array(stableId).optional(),
}).strict() as unknown as ZodType<ReleaseLinkRequest>;
