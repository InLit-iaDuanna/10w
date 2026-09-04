import type {
  AcquireLockRequest,
  ActivityRecord,
  AddCommentRequest,
  ApprovalObservation,
  AssetLockRecord,
  AssignmentRecord,
  AssignmentRequest,
  CreateReviewCommand,
  DecisionRecord,
  DecisionRequest,
  ExecuteRollbackRequest,
  ObserveApprovalRequest,
  ProposeRollbackRequest,
  ReleaseEvidenceLink,
  ReleaseLinkRequest,
  ReleaseLockRequest,
  ReviewComment,
  ReviewConversationSummary,
  ReviewSession,
  RollbackExecution,
  RollbackProposal,
} from "./generated/api-types.ts";

export interface VersionCollaborationApi {
  createReview(input: CreateReviewCommand): Promise<ReviewSession>;
  getReview(reviewId: string): Promise<ReviewSession>;
  getReviewRevision(reviewId: string, reviewRevisionId: string): Promise<ReviewSession>;
  getSummary(reviewId: string): Promise<ReviewConversationSummary>;
  getRevisionSummary(reviewId: string, reviewRevisionId: string): Promise<ReviewConversationSummary>;
  listActivity(reviewId: string): Promise<readonly ActivityRecord[]>;
  listComments(reviewId: string): Promise<readonly ReviewComment[]>;
  listAssignments(reviewId: string): Promise<readonly AssignmentRecord[]>;
  listDecisions(reviewId: string): Promise<readonly DecisionRecord[]>;
  listApprovals(reviewId: string): Promise<readonly ApprovalObservation[]>;
  listActiveLocks(projectId: string): Promise<readonly AssetLockRecord[]>;
  listReleaseLinks(reviewId: string): Promise<readonly ReleaseEvidenceLink[]>;
  addComment(reviewId: string, input: AddCommentRequest): Promise<ReviewComment>;
  recordAssignment(reviewId: string, input: AssignmentRequest): Promise<AssignmentRecord>;
  recordDecision(reviewId: string, input: DecisionRequest): Promise<DecisionRecord>;
  observeApproval(reviewId: string, input: ObserveApprovalRequest): Promise<ApprovalObservation>;
  acquireLock(input: AcquireLockRequest): Promise<AssetLockRecord>;
  releaseLock(input: ReleaseLockRequest): Promise<AssetLockRecord>;
  proposeRollback(input: ProposeRollbackRequest): Promise<RollbackProposal>;
  executeRollback(input: ExecuteRollbackRequest): Promise<RollbackExecution>;
  linkRelease(input: ReleaseLinkRequest): Promise<ReleaseEvidenceLink>;
}
