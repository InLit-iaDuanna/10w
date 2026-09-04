import type {
  IntakeFieldKey,
  IntakeValidationIssue,
  ProjectIntakeRecord,
  ProjectRoot,
  TrackedField,
} from "./contracts.ts";

const windowsAbsolutePath = /^[A-Za-z]:[\\/]/;

export function isAbsoluteProjectPath(value: string): boolean {
  return value.startsWith("/") || value.startsWith("\\\\") || windowsAbsolutePath.test(value);
}

function hasValues<T>(field: TrackedField<readonly T[]>): boolean {
  return field.value !== null && field.value.length > 0;
}

export function validateProjectRoot(root: ProjectRoot | null): IntakeValidationIssue | null {
  if (root === null || root.absolutePath.trim().length === 0) {
    return {
      code: "MISSING_PROJECT_ROOT",
      field: "projectRoots",
      message: "请选择项目根目录。",
    };
  }
  if (!isAbsoluteProjectPath(root.absolutePath)) {
    return {
      code: "INVALID_PROJECT_ROOT",
      field: "projectRoots",
      message: "项目根目录必须是绝对路径。",
    };
  }
  return null;
}

export function validateIntakeForActivation(
  record: ProjectIntakeRecord,
): readonly IntakeValidationIssue[] {
  const issues: IntakeValidationIssue[] = [];
  const { projectName, targetPlatforms, projectRoots } = record.fields;

  if (projectName.value === null || projectName.value.trim().length === 0) {
    issues.push({
      code: "MISSING_PROJECT_NAME",
      field: "projectName",
      message: "请输入项目名称。",
    });
  }
  if (!hasValues(targetPlatforms)) {
    issues.push({
      code: "MISSING_TARGET_PLATFORM",
      field: "targetPlatforms",
      message: "至少选择一个目标平台。",
    });
  } else if (targetPlatforms.confidence !== "confirmed") {
    issues.push({
      code: "TARGET_PLATFORM_NOT_CONFIRMED",
      field: "targetPlatforms",
      message: "目标平台来自推断，请由用户确认。",
    });
  }

  if (!hasValues(projectRoots)) {
    issues.push({
      code: "MISSING_PROJECT_ROOT",
      field: "projectRoots",
      message: "请选择项目根目录。",
    });
  } else {
    for (const root of projectRoots.value ?? []) {
      const rootIssue = validateProjectRoot(root);
      if (rootIssue !== null) issues.push(rootIssue);
    }
    if (projectRoots.confidence !== "confirmed") {
      issues.push({
        code: "PROJECT_ROOT_NOT_CONFIRMED",
        field: "projectRoots",
        message: "项目根目录来自推断，请由用户确认。",
      });
    }
  }
  return issues;
}

export function listFieldsByConfidence(
  record: ProjectIntakeRecord,
  confidence: "inferred" | "missing",
): readonly IntakeFieldKey[] {
  return (Object.keys(record.fields) as IntakeFieldKey[]).filter(
    (key) => record.fields[key].confidence === confidence,
  );
}
