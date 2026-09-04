export const reviewKeys = {
  all: ["version-collaboration", "reviews"] as const,
  detail: (reviewId: string) => [...reviewKeys.all, "detail", reviewId] as const,
  revision: (reviewId: string, reviewRevisionId: string) =>
    [...reviewKeys.all, "revision", reviewId, reviewRevisionId] as const,
  summary: (reviewId: string) => [...reviewKeys.all, "summary", reviewId] as const,
  activity: (reviewId: string) => [...reviewKeys.all, "activity", reviewId] as const,
  conversation: (reviewId: string) =>
    [...reviewKeys.all, "conversation", reviewId] as const,
  locks: (projectId: string) =>
    ["version-collaboration", "locks", projectId] as const,
};
