import { validateIntakeForActivation } from "../../../project-intake/frontend/src/index.ts";
import type {
  DesignValidationIssue,
  FeatureSpec,
  ProjectIntakeRecord,
} from "./contracts.ts";

const missingText = (value: string): boolean => value.trim().length === 0;

export function validateFeatureSpec(spec: FeatureSpec): readonly DesignValidationIssue[] {
  const issues: DesignValidationIssue[] = [];
  if (missingText(spec.title)) {
    issues.push({ code: "MISSING_FEATURE_TITLE", path: "/title", message: "请输入功能名称。" });
  }
  if (missingText(spec.goal)) {
    issues.push({ code: "MISSING_FEATURE_GOAL", path: "/goal", message: "请输入可验证的功能目标。" });
  }
  if (spec.inputs.length === 0) {
    issues.push({ code: "MISSING_INPUT", path: "/inputs", message: "至少定义一个输入。" });
  }
  if (spec.outputs.length === 0) {
    issues.push({ code: "MISSING_OUTPUT", path: "/outputs", message: "至少定义一个输出。" });
  }
  if (spec.acceptanceCriteria.length === 0) {
    issues.push({
      code: "MISSING_ACCEPTANCE_CRITERIA",
      path: "/acceptanceCriteria",
      message: "至少定义一条验收标准。",
    });
  }
  spec.acceptanceCriteria.forEach((criterion, index) => {
    if ([criterion.title, criterion.given, criterion.when, criterion.then].some(missingText)) {
      issues.push({
        code: "INCOMPLETE_ACCEPTANCE_CRITERION",
        path: `/acceptanceCriteria/${index}`,
        message: `验收标准 ${criterion.criterionId} 必须包含标题、Given、When 和 Then。`,
      });
    }
  });
  if (spec.requiredTests.length === 0) {
    issues.push({
      code: "MISSING_REQUIRED_TEST",
      path: "/requiredTests",
      message: "至少定义一个验证该功能的测试。",
    });
  }
  spec.assumptions.forEach((assumption, index) => {
    if (assumption.status === "unconfirmed") {
      issues.push({
        code: "UNCONFIRMED_ASSUMPTION",
        path: `/assumptions/${index}`,
        message: `假设 ${assumption.id} 尚未确认或拒绝。`,
      });
    }
  });
  return issues;
}

export function validateFeatureForPlanning(
  spec: FeatureSpec,
  intake: ProjectIntakeRecord,
): readonly DesignValidationIssue[] {
  const issues = [...validateFeatureSpec(spec)];
  const intakeIssues = validateIntakeForActivation(intake);
  if (intakeIssues.length > 0 || intake.projectId !== spec.projectId) {
    issues.unshift({
      code: "PROJECT_INTAKE_NOT_READY",
      path: "/projectIntake",
      message:
        intake.projectId !== spec.projectId
          ? "项目入口与 Feature Spec 不属于同一项目。"
          : `项目入口尚未准备好：${intakeIssues.map((issue) => issue.message).join("；")}`,
    });
  }
  return issues;
}
