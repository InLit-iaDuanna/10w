import before from "../../../contracts/examples/find-my-way-home-before.runtime.json";
import after from "../../../contracts/examples/find-my-way-home-after.runtime.json";
import warehouse from "../../../contracts/examples/warehouse-escape.runtime.json";
import homeCase from "../../../contracts/examples/find-my-way-home-key-door.test-case.json";
import warehouseCase from "../../../contracts/examples/warehouse-escape.test-case.json";
import catalog from "../../../contracts/examples/source-catalog.v1.json";

// Read fixture snapshots only. These are authored observations, not runner outputs.
export const evidenceSamples = [
  { id: "sample.home.before", title: "家门交互 · 修复前样例", project: "Find My Way Home", fixture: before, testCase: homeCase, filename: "find-my-way-home-before.runtime.json" },
  { id: "sample.home.after", title: "家门交互 · 修复后样例", project: "Find My Way Home", fixture: after, testCase: homeCase, filename: "find-my-way-home-after.runtime.json" },
  { id: "sample.warehouse", title: "仓库出口 · 路径受阻样例", project: "Warehouse Escape", fixture: warehouse, testCase: warehouseCase, filename: "warehouse-escape.runtime.json" },
];
export type EvidenceSample = (typeof evidenceSamples)[number];
export type SampleFrame = EvidenceSample["fixture"]["frames"][number];
export const sourceRecords = Object.values(catalog.records);

// Authored review examples point to existing fixture observations; no detector runs here.
export const reviewExamples = [
  { id: "review.home.collider", sampleId: "sample.home.before", frame: 3, title: "钥匙在手，家门交互被碰撞体遮挡", kind: "collider_error", severity: "error", sourceId: "source-record.home-door.before", confidence: 0.85, reason: "样例 target sceneops_id、故障类别与构建一致；仍需人工核对真实源码。" },
  { id: "review.home.feedback", sampleId: "sample.home.before", frame: 4, title: "再次开门没有交互反馈", kind: "missing_feedback", severity: "warning", sourceId: null, confidence: 0, reason: "静态样例未提供唯一源记录，不能确认回钉或生成目标修复提案。" },
  { id: "review.warehouse.navigation", sampleId: "sample.warehouse", frame: 2, title: "出口路线与托盘碰撞体相交", kind: "navigation_error", severity: "error", sourceId: "source-record.warehouse-obstacle.fixture", confidence: 0.7, reason: "样例源对象声明与出口的关联；这是 Mock 因果候选。" },
];
export type ReviewExample = (typeof reviewExamples)[number];
export type LocalReview = { decision: "confirmed" | "rejected"; note: string; reviewedAt: string };
export type ProposalDraft = {
  id: string; sourceReviewId: string; targetId: string; owningModule: string;
  baseVersion: string; previousValue: string; proposedValue: string;
  rationale: string; expectedResult: string; risk: "medium";
  validationPlan: string; rollbackPlan: string; approvalRequirements: string[];
  executionMode: "planned"; submitted: false;
};

export const goalLabels: Record<string, string> = { pending: "未开始", in_progress: "进行中", completed: "样例目标完成", blocked: "目标受阻" };
