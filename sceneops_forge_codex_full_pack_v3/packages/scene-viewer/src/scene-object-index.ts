import {
  cloneMatrix4,
  IDENTITY_MATRIX4,
  type Matrix4,
} from './spatial.ts';

export type SceneOpsId = string;

export interface SceneNodeDescriptor {
  readonly nodeKey: string;
  readonly name: string;
  readonly extras: Readonly<Record<string, unknown>>;
  readonly parentNodeKey?: string;
  readonly localMatrix?: Matrix4;
  readonly assetId?: string;
}

export interface SceneObjectRecord {
  readonly sceneopsId: SceneOpsId;
  readonly nodeKey: string;
  readonly name: string;
  readonly parentSceneopsId: SceneOpsId | null;
  readonly localMatrix: Matrix4;
  readonly assetId: string | null;
  readonly copiedFromSceneopsId: SceneOpsId | null;
}

export interface SceneObjectCopyRequest {
  readonly sourceSceneopsId: SceneOpsId;
  readonly newSceneopsId: SceneOpsId;
  readonly newNodeKey: string;
  readonly name?: string;
  readonly parentSceneopsId?: SceneOpsId | null;
}

export type SceneIdentityErrorCode =
  | 'INVALID_SCENEOPS_ID'
  | 'MISSING_SCENEOPS_ID'
  | 'DUPLICATE_SCENEOPS_ID'
  | 'DUPLICATE_NODE_KEY'
  | 'UNKNOWN_NODE'
  | 'UNKNOWN_SCENE_OBJECT'
  | 'INVALID_NAME'
  | 'IDENTITY_REUSE'
  | 'CYCLIC_HIERARCHY';

export class SceneIdentityError extends Error {
  readonly code: SceneIdentityErrorCode;

  constructor(code: SceneIdentityErrorCode, message: string) {
    super(message);
    this.name = 'SceneIdentityError';
    this.code = code;
  }
}

export class SceneObjectIndex {
  readonly #bySceneopsId: Map<SceneOpsId, SceneObjectRecord>;
  readonly #sceneopsIdByNodeKey: Map<string, SceneOpsId>;

  constructor(records: readonly SceneObjectRecord[]) {
    this.#bySceneopsId = new Map();
    this.#sceneopsIdByNodeKey = new Map();
    for (const record of records) this.#insert(freezeRecord(record));
    assertAcyclic(this.#bySceneopsId);
  }

  get size(): number {
    return this.#bySceneopsId.size;
  }

  has(sceneopsId: SceneOpsId): boolean {
    return this.#bySceneopsId.has(sceneopsId);
  }

  get(sceneopsId: SceneOpsId): SceneObjectRecord | undefined {
    return this.#bySceneopsId.get(sceneopsId);
  }

  require(sceneopsId: SceneOpsId): SceneObjectRecord {
    const record = this.get(sceneopsId);
    if (!record) {
      throw new SceneIdentityError(
        'UNKNOWN_SCENE_OBJECT',
        `Unknown scene object: ${sceneopsId}`,
      );
    }
    return record;
  }

  sceneopsIdForNode(nodeKey: string): SceneOpsId {
    const sceneopsId = this.#sceneopsIdByNodeKey.get(nodeKey);
    if (!sceneopsId) {
      throw new SceneIdentityError('UNKNOWN_NODE', `Unknown scene node: ${nodeKey}`);
    }
    return sceneopsId;
  }

  list(): readonly SceneObjectRecord[] {
    return Object.freeze([...this.#bySceneopsId.values()]);
  }

  rename(sceneopsId: SceneOpsId, newName: string): SceneObjectRecord {
    const current = this.require(sceneopsId);
    assertName(newName);
    const renamed = freezeRecord({ ...current, name: newName });
    this.#bySceneopsId.set(sceneopsId, renamed);
    return renamed;
  }

  copy(request: SceneObjectCopyRequest): SceneObjectRecord {
    const source = this.require(request.sourceSceneopsId);
    assertSceneopsId(request.newSceneopsId);
    assertNodeKey(request.newNodeKey);
    if (request.newSceneopsId === source.sceneopsId) {
      throw new SceneIdentityError('IDENTITY_REUSE', 'A copied object requires a new sceneops_id.');
    }
    if (this.#bySceneopsId.has(request.newSceneopsId)) {
      throw new SceneIdentityError(
        'DUPLICATE_SCENEOPS_ID',
        `Duplicate sceneops_id: ${request.newSceneopsId}`,
      );
    }
    if (this.#sceneopsIdByNodeKey.has(request.newNodeKey)) {
      throw new SceneIdentityError(
        'DUPLICATE_NODE_KEY',
        `Duplicate nodeKey: ${request.newNodeKey}`,
      );
    }

    const parentSceneopsId = request.parentSceneopsId === undefined
      ? source.parentSceneopsId
      : request.parentSceneopsId;
    if (parentSceneopsId !== null) this.require(parentSceneopsId);
    const name = request.name ?? `${source.name} Copy`;
    assertName(name);

    const copied = freezeRecord({
      sceneopsId: request.newSceneopsId,
      nodeKey: request.newNodeKey,
      name,
      parentSceneopsId,
      localMatrix: source.localMatrix,
      assetId: source.assetId,
      copiedFromSceneopsId: source.sceneopsId,
    });
    this.#insert(copied);
    return copied;
  }

  #insert(record: SceneObjectRecord): void {
    assertSceneopsId(record.sceneopsId);
    assertNodeKey(record.nodeKey);
    assertName(record.name);
    if (this.#bySceneopsId.has(record.sceneopsId)) {
      throw new SceneIdentityError(
        'DUPLICATE_SCENEOPS_ID',
        `Duplicate sceneops_id: ${record.sceneopsId}`,
      );
    }
    if (this.#sceneopsIdByNodeKey.has(record.nodeKey)) {
      throw new SceneIdentityError(
        'DUPLICATE_NODE_KEY',
        `Duplicate nodeKey: ${record.nodeKey}`,
      );
    }
    this.#bySceneopsId.set(record.sceneopsId, record);
    this.#sceneopsIdByNodeKey.set(record.nodeKey, record.sceneopsId);
  }
}

export function loadSceneObjectIndex(
  nodes: readonly SceneNodeDescriptor[],
): SceneObjectIndex {
  const idsByNodeKey = new Map<string, SceneOpsId>();
  for (const node of nodes) {
    assertNodeKey(node.nodeKey);
    if (idsByNodeKey.has(node.nodeKey)) {
      throw new SceneIdentityError('DUPLICATE_NODE_KEY', `Duplicate nodeKey: ${node.nodeKey}`);
    }
    idsByNodeKey.set(node.nodeKey, readSceneopsId(node));
  }

  const records = nodes.map((node): SceneObjectRecord => {
    const parentSceneopsId = node.parentNodeKey === undefined
      ? null
      : idsByNodeKey.get(node.parentNodeKey);
    if (node.parentNodeKey !== undefined && parentSceneopsId === undefined) {
      throw new SceneIdentityError(
        'UNKNOWN_NODE',
        `Node ${node.nodeKey} has unknown parent ${node.parentNodeKey}.`,
      );
    }
    return {
      sceneopsId: idsByNodeKey.get(node.nodeKey)!,
      nodeKey: node.nodeKey,
      name: node.name,
      parentSceneopsId: parentSceneopsId ?? null,
      localMatrix: node.localMatrix ?? IDENTITY_MATRIX4,
      assetId: node.assetId ?? null,
      copiedFromSceneopsId: null,
    };
  });
  return new SceneObjectIndex(records);
}

function readSceneopsId(node: SceneNodeDescriptor): SceneOpsId {
  const value = node.extras.sceneops_id;
  if (value === undefined) {
    throw new SceneIdentityError(
      'MISSING_SCENEOPS_ID',
      `Node ${node.nodeKey} does not declare extras.sceneops_id.`,
    );
  }
  if (typeof value !== 'string') {
    throw new SceneIdentityError(
      'INVALID_SCENEOPS_ID',
      `Node ${node.nodeKey} has a non-string sceneops_id.`,
    );
  }
  assertSceneopsId(value);
  return value;
}

function freezeRecord(record: SceneObjectRecord): SceneObjectRecord {
  return Object.freeze({ ...record, localMatrix: cloneMatrix4(record.localMatrix) });
}

function assertSceneopsId(sceneopsId: string): void {
  if (sceneopsId.length === 0 || sceneopsId.trim() !== sceneopsId) {
    throw new SceneIdentityError(
      'INVALID_SCENEOPS_ID',
      'sceneops_id must be a non-empty, trimmed string.',
    );
  }
}

function assertNodeKey(nodeKey: string): void {
  if (nodeKey.length === 0 || nodeKey.trim() !== nodeKey) {
    throw new SceneIdentityError('UNKNOWN_NODE', 'nodeKey must be a non-empty, trimmed string.');
  }
}

function assertName(name: string): void {
  if (name.trim().length === 0) {
    throw new SceneIdentityError('INVALID_NAME', 'Scene object name must not be blank.');
  }
}

function assertAcyclic(records: ReadonlyMap<SceneOpsId, SceneObjectRecord>): void {
  for (const startingId of records.keys()) {
    const visited = new Set<SceneOpsId>();
    let currentId: SceneOpsId | null = startingId;
    while (currentId !== null) {
      if (visited.has(currentId)) {
        throw new SceneIdentityError(
          'CYCLIC_HIERARCHY',
          `Scene hierarchy contains a cycle at ${currentId}.`,
        );
      }
      visited.add(currentId);
      const current = records.get(currentId);
      if (!current) {
        throw new SceneIdentityError(
          'UNKNOWN_SCENE_OBJECT',
          `Unknown parent scene object: ${currentId}`,
        );
      }
      currentId = current.parentSceneopsId;
    }
  }
}
