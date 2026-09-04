import type { DecisionRecord } from "./contracts.ts";
import { DesignRoomError } from "./contracts.ts";

function assertOpen(record: DecisionRecord): void {
  if (record.status === "decided") {
    throw new DesignRoomError("DECISION_ALREADY_FINAL", "该决策已经完成。", {
      decisionId: record.decisionId,
    });
  }
}

function assertRationale(rationale: string): void {
  if (rationale.trim().length === 0) {
    throw new DesignRoomError("INVALID_DECISION_RATIONALE", "接受或拒绝方案时必须记录理由。");
  }
}

export function rejectDecisionAlternative(
  record: DecisionRecord,
  alternativeId: string,
  rationale: string,
): DecisionRecord {
  assertOpen(record);
  assertRationale(rationale);
  const alternative = record.alternatives.find((item) => item.alternativeId === alternativeId);
  if (alternative === undefined) {
    throw new DesignRoomError("ALTERNATIVE_NOT_FOUND", "找不到待拒绝的方案。", { alternativeId });
  }
  return {
    ...record,
    alternatives: record.alternatives.map((item) =>
      item.alternativeId === alternativeId
        ? { ...item, disposition: "rejected", rationale }
        : item,
    ),
  };
}

export function acceptDecisionAlternative(
  record: DecisionRecord,
  alternativeId: string,
  rationale: string,
  actorId: string,
  occurredAt: string,
): DecisionRecord {
  assertOpen(record);
  assertRationale(rationale);
  const selected = record.alternatives.find((item) => item.alternativeId === alternativeId);
  if (selected === undefined) {
    throw new DesignRoomError("ALTERNATIVE_NOT_FOUND", "找不到待接受的方案。", { alternativeId });
  }
  const pendingOthers = record.alternatives.filter(
    (item) => item.alternativeId !== alternativeId && item.disposition !== "rejected",
  );
  if (pendingOthers.length > 0) {
    throw new DesignRoomError("PENDING_ALTERNATIVES", "接受方案前必须逐项拒绝其余方案并记录理由。", {
      alternativeIds: pendingOthers.map((item) => item.alternativeId),
    });
  }
  return {
    ...record,
    status: "decided",
    alternatives: record.alternatives.map((item) =>
      item.alternativeId === alternativeId
        ? { ...item, disposition: "accepted", rationale }
        : item,
    ),
    decidedBy: actorId,
    decidedAt: occurredAt,
  };
}
