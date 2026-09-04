import { isJsonValue } from "../contracts/json.ts";
import {
  assistantActionTypes,
  type AssistantAction,
  type AssistantActionType,
} from "./types.ts";

export interface ActionValidationIssue {
  path: string;
  code: "invalid_type" | "invalid_value" | "missing" | "unknown_field";
  message: string;
}

export type ActionValidationResult =
  | { ok: true; value: AssistantAction }
  | { ok: false; issues: ActionValidationIssue[] };

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function addUnknownFieldIssues(
  value: UnknownRecord,
  allowed: readonly string[],
  path: string,
  issues: ActionValidationIssue[],
): void {
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) {
      issues.push({
        path: `${path}.${key}`,
        code: "unknown_field",
        message: `不支持字段 ${key}`,
      });
    }
  }
}

function requireString(
  value: UnknownRecord,
  key: string,
  path: string,
  issues: ActionValidationIssue[],
  options: { pattern?: RegExp; minLength?: number; maxLength?: number } = {},
): void {
  const candidate = value[key];
  if (typeof candidate !== "string" || candidate.length === 0) {
    issues.push({
      path: `${path}.${key}`,
      code: candidate === undefined ? "missing" : "invalid_type",
      message: `${key} 必须是非空字符串`,
    });
    return;
  }

  if (options.maxLength !== undefined && candidate.length > options.maxLength) {
    issues.push({
      path: `${path}.${key}`,
      code: "invalid_value",
      message: `${key} 不能超过 ${options.maxLength} 个字符`,
    });
  }

  if (options.minLength !== undefined && candidate.length < options.minLength) {
    issues.push({
      path: `${path}.${key}`,
      code: "invalid_value",
      message: `${key} 不能少于 ${options.minLength} 个字符`,
    });
  }

  if (options.pattern && !options.pattern.test(candidate)) {
    issues.push({
      path: `${path}.${key}`,
      code: "invalid_value",
      message: `${key} 格式不正确`,
    });
  }
}

function optionalString(
  value: UnknownRecord,
  key: string,
  path: string,
  issues: ActionValidationIssue[],
  maxLength: number,
  minLength = 1,
): void {
  if (value[key] === undefined) {
    return;
  }

  requireString(value, key, path, issues, { minLength, maxLength });
}

function validateBase(
  value: UnknownRecord,
  issues: ActionValidationIssue[],
): AssistantActionType | null {
  requireString(value, "actionId", "$", issues, {
    pattern: /^act_[A-Za-z0-9_-]+$/,
    maxLength: 160,
  });
  requireString(value, "title", "$", issues, { maxLength: 120 });

  const type = value.type;
  if (
    typeof type !== "string" ||
    !(assistantActionTypes as readonly string[]).includes(type)
  ) {
    issues.push({
      path: "$.type",
      code: type === undefined ? "missing" : "invalid_value",
      message: "type 不是允许的 Workbench command ID",
    });
    return null;
  }

  if (!isRecord(value.input)) {
    issues.push({
      path: "$.input",
      code: value.input === undefined ? "missing" : "invalid_type",
      message: "input 必须是对象",
    });
  }

  return type as AssistantActionType;
}

function validateContext(
  value: unknown,
  issues: ActionValidationIssue[],
): void {
  if (value === undefined) {
    return;
  }

  if (!isRecord(value)) {
    issues.push({
      path: "$.input.context",
      code: "invalid_type",
      message: "context 必须是对象",
    });
    return;
  }

  const allowed = [
    "projectId",
    "sceneId",
    "sceneObjectIds",
    "featureId",
    "buildId",
    "issueId",
  ] as const;
  addUnknownFieldIssues(value, allowed, "$.input.context", issues);

  for (const key of allowed.filter((candidate) => candidate !== "sceneObjectIds")) {
    optionalString(value, key, "$.input.context", issues, 160, 3);
  }

  if (value.sceneObjectIds !== undefined) {
    if (
      !Array.isArray(value.sceneObjectIds) ||
      value.sceneObjectIds.some(
        (item) => typeof item !== "string" || item.length < 3,
      )
    ) {
      issues.push({
        path: "$.input.context.sceneObjectIds",
        code: "invalid_type",
        message: "sceneObjectIds 必须是 stable ID 字符串数组",
      });
    } else if (new Set(value.sceneObjectIds).size !== value.sceneObjectIds.length) {
      issues.push({
        path: "$.input.context.sceneObjectIds",
        code: "invalid_value",
        message: "sceneObjectIds 不能包含重复 ID",
      });
    }
  }
}

function validatePlacement(
  value: unknown,
  issues: ActionValidationIssue[],
): void {
  if (!isRecord(value)) {
    issues.push({
      path: "$.input.placement",
      code: value === undefined ? "missing" : "invalid_type",
      message: "placement 必须是对象",
    });
    return;
  }

  const mode = value.mode;
  const modes = ["replace", "tab", "split", "floating", "popout", "drawer"];
  if (typeof mode !== "string" || !modes.includes(mode)) {
    issues.push({
      path: "$.input.placement.mode",
      code: mode === undefined ? "missing" : "invalid_value",
      message: "placement.mode 不受支持",
    });
    return;
  }

  if (mode === "split") {
    addUnknownFieldIssues(
      value,
      ["mode", "direction", "relativeToInstanceId"],
      "$.input.placement",
      issues,
    );
    if (!["left", "right", "above", "below"].includes(String(value.direction))) {
      issues.push({
        path: "$.input.placement.direction",
        code: value.direction === undefined ? "missing" : "invalid_value",
        message: "split 必须声明有效 direction",
      });
    }
    optionalString(value, "relativeToInstanceId", "$.input.placement", issues, 160, 3);
    return;
  }

  if (mode === "drawer") {
    addUnknownFieldIssues(value, ["mode", "edge"], "$.input.placement", issues);
    if (!["left", "right", "top", "bottom"].includes(String(value.edge))) {
      issues.push({
        path: "$.input.placement.edge",
        code: value.edge === undefined ? "missing" : "invalid_value",
        message: "drawer 必须声明有效 edge",
      });
    }
    return;
  }

  const allowed = mode === "replace" || mode === "tab"
    ? ["mode", "relativeToInstanceId"]
    : ["mode"];
  addUnknownFieldIssues(value, allowed, "$.input.placement", issues);
  optionalString(value, "relativeToInstanceId", "$.input.placement", issues, 160, 3);
}

function validateOpenEditor(
  root: UnknownRecord,
  input: UnknownRecord,
  issues: ActionValidationIssue[],
): void {
  addUnknownFieldIssues(
    root,
    ["actionId", "type", "title", "requiresConfirmation", "input"],
    "$",
    issues,
  );
  if (root.requiresConfirmation !== true) {
    issues.push({
      path: "$.requiresConfirmation",
      code: root.requiresConfirmation === undefined ? "missing" : "invalid_value",
      message: "打开工具必须显式要求布局确认",
    });
  }
  addUnknownFieldIssues(input, ["editorId", "placement", "context"], "$.input", issues);
  requireString(input, "editorId", "$.input", issues, {
    minLength: 3,
    maxLength: 160,
  });
  validatePlacement(input.placement, issues);
  validateContext(input.context, issues);
}

function validateTypedInput(
  type: AssistantActionType,
  input: UnknownRecord,
  issues: ActionValidationIssue[],
): void {
  const requireId = (key: string) =>
    requireString(input, key, "$.input", issues, {
      minLength: 3,
      maxLength: 160,
    });

  if (type === "project.create") {
    addUnknownFieldIssues(
      input,
      ["changeSetId", "name", "brief", "sourceAttachmentId"],
      "$.input",
      issues,
    );
    requireId("changeSetId");
    requireString(input, "name", "$.input", issues, { maxLength: 120 });
    optionalString(input, "brief", "$.input", issues, 12000);
    optionalString(input, "sourceAttachmentId", "$.input", issues, 160, 3);
  } else if (type === "feature.create") {
    addUnknownFieldIssues(
      input,
      ["changeSetId", "projectId", "title", "brief"],
      "$.input",
      issues,
    );
    requireId("changeSetId");
    requireId("projectId");
    requireString(input, "title", "$.input", issues, { maxLength: 160 });
    requireString(input, "brief", "$.input", issues, { maxLength: 12000 });
  } else if (type === "workflow.run") {
    addUnknownFieldIssues(
      input,
      ["changeSetId", "projectId", "workflowId", "parameters"],
      "$.input",
      issues,
    );
    requireId("changeSetId");
    requireId("projectId");
    requireId("workflowId");
    if (!isRecord(input.parameters) || !isJsonValue(input.parameters)) {
      issues.push({
        path: "$.input.parameters",
        code: input.parameters === undefined ? "missing" : "invalid_type",
        message: "parameters 必须是 JSON 对象",
      });
    }
  } else if (type === "artifact.open") {
    addUnknownFieldIssues(input, ["artifactId", "preferredEditorId"], "$.input", issues);
    requireId("artifactId");
    optionalString(input, "preferredEditorId", "$.input", issues, 160, 3);
  } else if (type === "issue.open_backpin") {
    addUnknownFieldIssues(input, ["issueId"], "$.input", issues);
    requireId("issueId");
  } else if (type === "changeset.approval.request") {
    addUnknownFieldIssues(input, ["changeSetId", "reason"], "$.input", issues);
    requireId("changeSetId");
    optionalString(input, "reason", "$.input", issues, 2000);
  }
}

export function validateAssistantAction(value: unknown): ActionValidationResult {
  if (!isRecord(value)) {
    return {
      ok: false,
      issues: [
        {
          path: "$",
          code: "invalid_type",
          message: "Assistant action 必须是对象",
        },
      ],
    };
  }

  const issues: ActionValidationIssue[] = [];
  const type = validateBase(value, issues);
  if (type && isRecord(value.input)) {
    if (type === "workbench.open_editor") {
      validateOpenEditor(value, value.input, issues);
    } else {
      addUnknownFieldIssues(value, ["actionId", "type", "title", "input"], "$", issues);
      validateTypedInput(type, value.input, issues);
    }
  }

  return issues.length === 0
    ? { ok: true, value: value as unknown as AssistantAction }
    : { ok: false, issues };
}
