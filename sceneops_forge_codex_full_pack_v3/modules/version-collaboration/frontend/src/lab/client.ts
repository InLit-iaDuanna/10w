import type { ApiOperations } from "../generated/api-types.ts";

/** Transport signatures are generated from the Python OpenAPI, not UI DTO copies. */
export function createReviewClient(fetchImpl: typeof fetch = fetch) {
async function reviewRequest<K extends keyof ApiOperations>(
  operation: K, params: ApiOperations[K]["params"], body: ApiOperations[K]["body"],
): Promise<ApiOperations[K]["response"]> {
  const [method, template] = operation.split(" ");
  const url = template.replace(/\{([^}]+)\}/g, (_, key: string) =>
    encodeURIComponent((params as Record<string, string>)[key]));
  const response = await fetchImpl(url, {
    method, headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.message ?? payload.error?.message ?? JSON.stringify(payload.detail ?? payload));
  return payload;
}

async function loadReview(review_id: string) {
  const params = { review_id };
  const [review, comments, decisions, approvals, activity] = await Promise.all([
    reviewRequest("GET /api/version-collaboration/reviews/{review_id}", params, undefined),
    reviewRequest("GET /api/version-collaboration/reviews/{review_id}/comments", params, undefined),
    reviewRequest("GET /api/version-collaboration/reviews/{review_id}/decisions", params, undefined),
    reviewRequest("GET /api/version-collaboration/reviews/{review_id}/approvals", params, undefined),
    reviewRequest("GET /api/version-collaboration/reviews/{review_id}/activity", params, undefined),
  ]);
  return { review, comments, decisions, approvals, activity };
}

return { reviewRequest, loadReview };
}
export const { reviewRequest, loadReview } = createReviewClient();
export type ReviewData = Awaited<ReturnType<typeof loadReview>>;
