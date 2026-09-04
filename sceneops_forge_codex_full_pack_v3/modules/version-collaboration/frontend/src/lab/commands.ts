import { commandDefinitions } from "../commands/definitions.ts";
import type { VersionCollaborationApi } from "../api.ts";
import type { AddCommentRequest, DecisionRequest } from "../generated/api-types.ts";
import { reviewRequest as request } from "./client.ts";

/** The standalone composition supplies the same API port as the shell editors. */
export function createReviewCommands(request: typeof import('./client').reviewRequest) {
const api: VersionCollaborationApi = {
  createReview: body => request("POST /api/version-collaboration/reviews", {}, body),
  getReview: review_id => request("GET /api/version-collaboration/reviews/{review_id}", { review_id }, undefined),
  getReviewRevision: (review_id, review_revision_id) => request("GET /api/version-collaboration/reviews/{review_id}/revisions/{review_revision_id}", { review_id, review_revision_id }, undefined),
  getSummary: review_id => request("GET /api/version-collaboration/reviews/{review_id}/summary", { review_id }, undefined),
  getRevisionSummary: (review_id, review_revision_id) => request("GET /api/version-collaboration/reviews/{review_id}/revisions/{review_revision_id}/summary", { review_id, review_revision_id }, undefined),
  listActivity: review_id => request("GET /api/version-collaboration/reviews/{review_id}/activity", { review_id }, undefined),
  listComments: review_id => request("GET /api/version-collaboration/reviews/{review_id}/comments", { review_id }, undefined),
  listAssignments: review_id => request("GET /api/version-collaboration/reviews/{review_id}/assignments", { review_id }, undefined),
  listDecisions: review_id => request("GET /api/version-collaboration/reviews/{review_id}/decisions", { review_id }, undefined),
  listApprovals: review_id => request("GET /api/version-collaboration/reviews/{review_id}/approvals", { review_id }, undefined),
  listActiveLocks: project_id => request("GET /api/version-collaboration/projects/{project_id}/locks", { project_id }, undefined),
  listReleaseLinks: review_id => request("GET /api/version-collaboration/reviews/{review_id}/release-links", { review_id }, undefined),
  addComment: (review_id, body) => request("POST /api/version-collaboration/reviews/{review_id}/comments", { review_id }, body),
  recordAssignment: (review_id, body) => request("POST /api/version-collaboration/reviews/{review_id}/assignments", { review_id }, body),
  recordDecision: (review_id, body) => request("POST /api/version-collaboration/reviews/{review_id}/decisions", { review_id }, body),
  observeApproval: (review_id, body) => request("POST /api/version-collaboration/reviews/{review_id}/approvals", { review_id }, body),
  acquireLock: body => request("POST /api/version-collaboration/locks/acquire", {}, body),
  releaseLock: body => request("POST /api/version-collaboration/locks/release", {}, body),
  proposeRollback: body => request("POST /api/version-collaboration/rollbacks/propose", {}, body),
  executeRollback: body => request("POST /api/version-collaboration/rollbacks/execute", {}, body),
  linkRelease: body => request("POST /api/version-collaboration/release-links", {}, body),
};

const context = {
  versionCollaborationApi: api,
  permissions: new Set(["review:read", "review:comment", "review:approve"]),
  integrations: new Set<string>(),
};

type Inputs = { "review.comment.add": AddCommentRequest; "review.decision.record": DecisionRequest };
function executeReviewCommand<K extends keyof Inputs>(id: K, reviewId: string, body: Inputs[K]) {
  const command = commandDefinitions.find(item => item.id === id)!;
  return command.execute(context, { reviewId, body });
}
return executeReviewCommand;
}
export const executeReviewCommand = createReviewCommands(request);
