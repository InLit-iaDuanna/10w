import type {
  ConversationProjectIntent,
  ExistingProjectScanInput,
  FieldEvidence,
  IntakeFieldKey,
  NewProjectIntakeInput,
  ProjectIntakeFields,
  ProjectIntakeRecord,
  ProjectIntakeValues,
  ProjectRoot,
  TrackedField,
} from "./contracts.ts";
import type { ProjectScanReport } from "./adapters/ProjectScanAdapter.ts";
import { validateIntakeForActivation } from "./validation.ts";

function missing<T>(): TrackedField<T> {
  return { value: null, confidence: "missing", evidence: null };
}

function tracked<T>(
  value: T | undefined,
  confidence: "confirmed" | "inferred",
  evidence: FieldEvidence,
  isEmpty: (candidate: T) => boolean,
): TrackedField<T> {
  if (value === undefined || isEmpty(value)) return missing<T>();
  return { value, confidence, evidence };
}

const emptyString = (value: string): boolean => value.trim().length === 0;
const emptyArray = <T>(value: readonly T[]): boolean => value.length === 0;
const neverEmpty = (): boolean => false;

function createFields(
  input: NewProjectIntakeInput,
  confidence: "confirmed" | "inferred",
  origin: FieldEvidence["origin"],
  reference: string,
): ProjectIntakeFields {
  const evidence: FieldEvidence = { origin, reference, observedAt: input.occurredAt };
  return {
    projectName: tracked(input.projectName, confidence, evidence, emptyString),
    targetPlatforms: tracked(input.targetPlatforms, confidence, evidence, emptyArray),
    engine: tracked(input.engine, confidence, evidence, neverEmpty),
    dccs: tracked(input.dccs, confidence, evidence, emptyArray),
    projectRoots: tracked(input.projectRoots, confidence, evidence, emptyArray),
    teamRoles: tracked(input.teamRoles, confidence, evidence, emptyArray),
    styleGoals: tracked(input.styleGoals, confidence, evidence, emptyArray),
    performanceBudgets: tracked(input.performanceBudgets, confidence, evidence, emptyArray),
    integrationRequirements: tracked(
      input.integrationRequirements,
      confidence,
      evidence,
      emptyArray,
    ),
  };
}

function deriveStatus(fields: ProjectIntakeFields, record: ProjectIntakeRecord): ProjectIntakeRecord["status"] {
  const candidate: ProjectIntakeRecord = { ...record, fields, status: "draft" };
  const issues = validateIntakeForActivation(candidate);
  if (issues.length === 0) return "ready";
  const hasInferredCritical = issues.some(
    (issue) =>
      issue.code === "TARGET_PLATFORM_NOT_CONFIRMED" ||
      issue.code === "PROJECT_ROOT_NOT_CONFIRMED",
  );
  return hasInferredCritical ? "needs-confirmation" : "draft";
}

function assembleRecord(
  input: NewProjectIntakeInput,
  kind: ProjectIntakeRecord["kind"],
  fields: ProjectIntakeFields,
  scanReference: ProjectIntakeRecord["scanReference"],
): ProjectIntakeRecord {
  const draft: ProjectIntakeRecord = {
    schemaVersion: 1,
    intakeId: input.intakeId,
    projectId: input.projectId,
    kind,
    status: "draft",
    fields,
    scanReference,
    mode: input.mode,
    createdAt: input.occurredAt,
    updatedAt: input.occurredAt,
  };
  return { ...draft, status: deriveStatus(fields, draft) };
}

export function createNewProjectIntake(input: NewProjectIntakeInput): ProjectIntakeRecord {
  const fields = createFields(input, "confirmed", "user", input.actorId);
  return assembleRecord(input, "new-project", fields, null);
}

export function createConversationProjectIntake(
  input: ConversationProjectIntent,
): ProjectIntakeRecord {
  const fields = createFields(input, "inferred", "conversation", input.sourceMessageId);
  return assembleRecord(input, "new-project", fields, null);
}

function reportValue<K extends IntakeFieldKey>(
  report: ProjectScanReport,
  key: K,
): ProjectIntakeValues[K] | undefined {
  return report.detected[key];
}

function scanField<K extends IntakeFieldKey>(
  report: ProjectScanReport,
  key: K,
): TrackedField<ProjectIntakeValues[K]> {
  const value = reportValue(report, key);
  if (value === undefined) return missing<ProjectIntakeValues[K]>();
  const isEmpty = typeof value === "string" ? value.trim().length === 0 : Array.isArray(value) && value.length === 0;
  if (isEmpty) return missing<ProjectIntakeValues[K]>();
  return {
    value,
    confidence: "inferred",
    evidence: {
      origin: "project-scan",
      reference: report.scanId,
      observedAt: report.scannedAt,
    },
  };
}

export function createExistingProjectIntake(
  input: ExistingProjectScanInput & { readonly projectRoot: ProjectRoot },
  report: ProjectScanReport,
): ProjectIntakeRecord {
  const userRoot: TrackedField<readonly ProjectRoot[]> = {
    value: [input.projectRoot],
    confidence: "confirmed",
    evidence: { origin: "user", reference: input.actorId, observedAt: input.occurredAt },
  };
  const fields: ProjectIntakeFields = {
    projectName: scanField(report, "projectName"),
    targetPlatforms: scanField(report, "targetPlatforms"),
    engine: scanField(report, "engine"),
    dccs: scanField(report, "dccs"),
    projectRoots: userRoot,
    teamRoles: scanField(report, "teamRoles"),
    styleGoals: scanField(report, "styleGoals"),
    performanceBudgets: scanField(report, "performanceBudgets"),
    integrationRequirements: scanField(report, "integrationRequirements"),
  };
  const normalized: NewProjectIntakeInput = {
    intakeId: input.intakeId,
    projectId: input.projectId,
    actorId: input.actorId,
    occurredAt: input.occurredAt,
    mode: report.mode,
  };
  return assembleRecord(normalized, "existing-project", fields, {
    adapterId: report.adapterId,
    adapterVersion: report.adapterVersion,
    scanId: report.scanId,
    scannedAt: report.scannedAt,
    mode: report.mode,
    warnings: report.warnings,
  });
}

export function confirmIntakeField<K extends IntakeFieldKey>(
  record: ProjectIntakeRecord,
  key: K,
  value: ProjectIntakeValues[K],
  actorId: string,
  occurredAt: string,
): ProjectIntakeRecord {
  const fields = {
    ...record.fields,
    [key]: {
      value,
      confidence: "confirmed",
      evidence: { origin: "user", reference: actorId, observedAt: occurredAt },
    },
  } as ProjectIntakeFields;
  const updated: ProjectIntakeRecord = { ...record, fields, updatedAt: occurredAt };
  return { ...updated, status: deriveStatus(fields, updated) };
}
