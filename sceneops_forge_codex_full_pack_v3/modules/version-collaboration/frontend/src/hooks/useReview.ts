import { useQuery } from "@tanstack/react-query";

import type { VersionCollaborationApi } from "../api.ts";
import { reviewKeys } from "./queryKeys.ts";

export { reviewKeys } from "./queryKeys.ts";

export function useReview(
  api: VersionCollaborationApi,
  reviewId: string | null,
  enabled = true,
  reviewRevisionId: string | null = null,
) {
  return useQuery({
    queryKey: reviewRevisionId
      ? reviewKeys.revision(reviewId ?? "none", reviewRevisionId)
      : reviewKeys.detail(reviewId ?? "none"),
    queryFn: () => reviewRevisionId
      ? api.getReviewRevision(requiredReviewId(reviewId), reviewRevisionId)
      : api.getReview(requiredReviewId(reviewId)),
    enabled: enabled && reviewId !== null,
  });
}

export function useReviewSummary(
  api: VersionCollaborationApi,
  reviewId: string | null,
  enabled = true,
  reviewRevisionId: string | null = null,
) {
  return useQuery({
    queryKey: reviewRevisionId
      ? [...reviewKeys.summary(reviewId ?? "none"), reviewRevisionId]
      : reviewKeys.summary(reviewId ?? "none"),
    queryFn: () => reviewRevisionId
      ? api.getRevisionSummary(requiredReviewId(reviewId), reviewRevisionId)
      : api.getSummary(requiredReviewId(reviewId)),
    enabled: enabled && reviewId !== null,
  });
}

export function useReviewConversation(
  api: VersionCollaborationApi,
  reviewId: string | null,
  enabled = true,
) {
  return useQuery({
    queryKey: reviewKeys.conversation(reviewId ?? "none"),
    queryFn: async () => {
      const id = requiredReviewId(reviewId);
      const [comments, assignments, decisions, approvals, releaseLinks] =
        await Promise.all([
          api.listComments(id),
          api.listAssignments(id),
          api.listDecisions(id),
          api.listApprovals(id),
          api.listReleaseLinks(id),
        ]);
      return { comments, assignments, decisions, approvals, releaseLinks };
    },
    enabled: enabled && reviewId !== null,
  });
}

export function useReviewActivity(
  api: VersionCollaborationApi,
  reviewId: string | null,
  enabled = true,
) {
  return useQuery({
    queryKey: reviewKeys.activity(reviewId ?? "none"),
    queryFn: () => api.listActivity(requiredReviewId(reviewId)),
    enabled: enabled && reviewId !== null,
  });
}

export function useActiveLocks(
  api: VersionCollaborationApi,
  projectId: string | null,
  enabled = true,
) {
  return useQuery({
    queryKey: reviewKeys.locks(projectId ?? "none"),
    queryFn: () => api.listActiveLocks(requiredProjectId(projectId)),
    enabled: enabled && projectId !== null,
  });
}

function requiredReviewId(reviewId: string | null): string {
  if (reviewId === null) throw new Error("REVIEW_CONTEXT_REQUIRED");
  return reviewId;
}

function requiredProjectId(projectId: string | null): string {
  if (projectId === null) throw new Error("PROJECT_CONTEXT_REQUIRED");
  return projectId;
}
