import type {
  DecisionRecord,
  DesignChangeSet,
  DocumentVersion,
  FeatureSpec,
  GddDocument,
  ProjectBible,
  StructuralDiffEntry,
  VersionedDesignDocument,
} from "./contracts.ts";
import { DesignRoomError } from "./contracts.ts";
import { structuralDiff } from "./structuralDiff.ts";

export interface SaveVersionInput<TDocument extends VersionedDesignDocument> {
  readonly versionId: string;
  readonly document: TDocument;
  readonly actorId: string;
  readonly createdAt: string;
  readonly rationale: string;
  readonly mode: DocumentVersion<TDocument>["mode"];
  readonly sourceChangeSetId: string | null;
}

function cloneValue<T>(value: T): T {
  if (Array.isArray(value)) return value.map((item) => cloneValue(item)) as T;
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, cloneValue(item)]),
    ) as T;
  }
  return value;
}

export function designDocumentId(document: VersionedDesignDocument): string {
  return document.documentType === "project-bible" ? document.bibleId : document.featureSpecId;
}

function historyKey(documentType: VersionedDesignDocument["documentType"], documentId: string): string {
  return `${documentType}:${documentId}`;
}

export class InMemoryDesignDocumentRepository {
  readonly #histories = new Map<string, DocumentVersion<VersionedDesignDocument>[]>();
  readonly #gdds = new Map<string, GddDocument>();
  readonly #decisions = new Map<string, DecisionRecord>();
  readonly #changeSets = new Map<string, DesignChangeSet>();

  saveVersion<TDocument extends VersionedDesignDocument>(
    input: SaveVersionInput<TDocument>,
  ): DocumentVersion<TDocument> {
    const documentId = designDocumentId(input.document);
    const key = historyKey(input.document.documentType, documentId);
    const history = this.#histories.get(key) ?? [];
    if (history.some((version) => version.versionId === input.versionId)) {
      throw new DesignRoomError("VERSION_ID_CONFLICT", `版本 ID 已存在：${input.versionId}`);
    }
    const version: DocumentVersion<TDocument> = {
      versionId: input.versionId,
      versionNumber: history.length + 1,
      documentType: input.document.documentType,
      documentId,
      document: cloneValue(input.document),
      actorId: input.actorId,
      createdAt: input.createdAt,
      rationale: input.rationale,
      mode: input.mode,
      sourceChangeSetId: input.sourceChangeSetId,
    };
    history.push(version as DocumentVersion<VersionedDesignDocument>);
    this.#histories.set(key, history);
    return cloneValue(version);
  }

  latest<TDocument extends VersionedDesignDocument>(
    documentType: TDocument["documentType"],
    documentId: string,
  ): DocumentVersion<TDocument> | null {
    const history = this.#histories.get(historyKey(documentType, documentId));
    const latest = history?.at(-1);
    return latest === undefined ? null : (cloneValue(latest) as DocumentVersion<TDocument>);
  }

  history<TDocument extends VersionedDesignDocument>(
    documentType: TDocument["documentType"],
    documentId: string,
  ): readonly DocumentVersion<TDocument>[] {
    const history = this.#histories.get(historyKey(documentType, documentId)) ?? [];
    return cloneValue(history) as DocumentVersion<TDocument>[];
  }

  diff(
    documentType: VersionedDesignDocument["documentType"],
    documentId: string,
    fromVersionId: string,
    toVersionId: string,
  ): readonly StructuralDiffEntry[] {
    const history = this.#histories.get(historyKey(documentType, documentId)) ?? [];
    const from = history.find((version) => version.versionId === fromVersionId);
    const to = history.find((version) => version.versionId === toVersionId);
    if (from === undefined || to === undefined) {
      throw new DesignRoomError("VERSION_NOT_FOUND", "找不到用于比较的文档版本。", {
        fromVersionId,
        toVersionId,
      });
    }
    return structuralDiff(from.document, to.document);
  }

  saveGdd(document: GddDocument): void {
    this.#gdds.set(document.gddId, cloneValue(document));
  }

  getGdd(gddId: string): GddDocument | null {
    const document = this.#gdds.get(gddId);
    return document === undefined ? null : cloneValue(document);
  }

  saveDecision(decision: DecisionRecord): void {
    this.#decisions.set(decision.decisionId, cloneValue(decision));
  }

  getDecision(decisionId: string): DecisionRecord | null {
    const decision = this.#decisions.get(decisionId);
    return decision === undefined ? null : cloneValue(decision);
  }

  saveChangeSet(changeSet: DesignChangeSet): void {
    this.#changeSets.set(changeSet.changeSetId, cloneValue(changeSet));
  }

  getChangeSet(changeSetId: string): DesignChangeSet | null {
    const changeSet = this.#changeSets.get(changeSetId);
    return changeSet === undefined ? null : cloneValue(changeSet);
  }
}

export type BibleVersion = DocumentVersion<ProjectBible>;
export type FeatureSpecVersion = DocumentVersion<FeatureSpec>;
