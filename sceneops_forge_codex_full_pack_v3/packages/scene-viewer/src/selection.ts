import {
  SceneIdentityError,
  type SceneObjectIndex,
  type SceneOpsId,
} from './scene-object-index.ts';

export type SelectionBindingMode = 'follow-global' | 'pinned';

export interface SceneSelectionState {
  readonly selectedSceneopsIds: readonly SceneOpsId[];
  readonly primarySceneopsId: SceneOpsId | null;
}

export interface SceneSelectionSnapshot {
  readonly bindingMode: SelectionBindingMode;
  readonly global: SceneSelectionState;
  readonly pinned: SceneSelectionState | null;
}

export class SceneSelectionModel {
  readonly #index: SceneObjectIndex;
  #global: SceneSelectionState = emptySelection();
  #pinned: SceneSelectionState | null = null;

  constructor(index: SceneObjectIndex) {
    this.#index = index;
  }

  get bindingMode(): SelectionBindingMode {
    return this.#pinned === null ? 'follow-global' : 'pinned';
  }

  get active(): SceneSelectionState {
    return this.#pinned ?? this.#global;
  }

  get global(): SceneSelectionState {
    return this.#global;
  }

  setGlobalSelection(
    sceneopsIds: readonly SceneOpsId[],
    primarySceneopsId?: SceneOpsId | null,
  ): SceneSelectionState {
    this.#global = this.#normalize(sceneopsIds, primarySceneopsId);
    return this.active;
  }

  selectOnly(sceneopsId: SceneOpsId): SceneSelectionState {
    return this.#setActive([sceneopsId], sceneopsId);
  }

  toggle(sceneopsId: SceneOpsId): SceneSelectionState {
    this.#assertKnown(sceneopsId);
    const current = this.active;
    const nextIds = current.selectedSceneopsIds.includes(sceneopsId)
      ? current.selectedSceneopsIds.filter((id) => id !== sceneopsId)
      : [...current.selectedSceneopsIds, sceneopsId];
    return this.#setActive(nextIds);
  }

  clear(): SceneSelectionState {
    return this.#setActive([]);
  }

  pin(
    sceneopsIds?: readonly SceneOpsId[],
    primarySceneopsId?: SceneOpsId | null,
  ): SceneSelectionState {
    const usesActiveSelection = sceneopsIds === undefined;
    const selectedIds = sceneopsIds ?? this.active.selectedSceneopsIds;
    const primary = usesActiveSelection && primarySceneopsId === undefined
      ? this.active.primarySceneopsId
      : primarySceneopsId;
    this.#pinned = this.#normalize(selectedIds, primary);
    return this.#pinned;
  }

  followGlobal(): SceneSelectionState {
    this.#pinned = null;
    return this.#global;
  }

  snapshot(): SceneSelectionSnapshot {
    return Object.freeze({
      bindingMode: this.bindingMode,
      global: cloneSelection(this.#global),
      pinned: this.#pinned === null ? null : cloneSelection(this.#pinned),
    });
  }

  restore(snapshot: SceneSelectionSnapshot): SceneSelectionState {
    const global = this.#normalize(
      snapshot.global.selectedSceneopsIds,
      snapshot.global.primarySceneopsId,
    );
    if (snapshot.bindingMode === 'follow-global') {
      if (snapshot.pinned !== null) {
        throw new SceneSelectionError(
          'INVALID_SELECTION_SNAPSHOT',
          'A follow-global snapshot cannot contain pinned selection.',
        );
      }
      this.#global = global;
      this.#pinned = null;
      return this.active;
    }
    if (snapshot.bindingMode !== 'pinned' || snapshot.pinned === null) {
      throw new SceneSelectionError(
        'INVALID_SELECTION_SNAPSHOT',
        'A pinned snapshot requires pinned selection.',
      );
    }
    const pinned = this.#normalize(
      snapshot.pinned.selectedSceneopsIds,
      snapshot.pinned.primarySceneopsId,
    );
    this.#global = global;
    this.#pinned = pinned;
    return this.active;
  }

  #setActive(
    sceneopsIds: readonly SceneOpsId[],
    primarySceneopsId?: SceneOpsId | null,
  ): SceneSelectionState {
    const next = this.#normalize(sceneopsIds, primarySceneopsId);
    if (this.#pinned === null) this.#global = next;
    else this.#pinned = next;
    return next;
  }

  #normalize(
    sceneopsIds: readonly SceneOpsId[],
    primarySceneopsId?: SceneOpsId | null,
  ): SceneSelectionState {
    const uniqueIds = [...new Set(sceneopsIds)];
    for (const sceneopsId of uniqueIds) this.#assertKnown(sceneopsId);
    const primary = primarySceneopsId === undefined
      ? (uniqueIds.at(-1) ?? null)
      : primarySceneopsId;
    if (primary !== null && !uniqueIds.includes(primary)) {
      throw new SceneSelectionError(
        'PRIMARY_NOT_SELECTED',
        `Primary object ${primary} is not part of the selection.`,
      );
    }
    return Object.freeze({
      selectedSceneopsIds: Object.freeze(uniqueIds),
      primarySceneopsId: primary,
    });
  }

  #assertKnown(sceneopsId: SceneOpsId): void {
    if (!this.#index.has(sceneopsId)) {
      throw new SceneIdentityError(
        'UNKNOWN_SCENE_OBJECT',
        `Unknown scene object: ${sceneopsId}`,
      );
    }
  }
}

export class SceneSelectionError extends Error {
  readonly code: 'PRIMARY_NOT_SELECTED' | 'INVALID_SELECTION_SNAPSHOT';

  constructor(
    code: 'PRIMARY_NOT_SELECTED' | 'INVALID_SELECTION_SNAPSHOT',
    message: string,
  ) {
    super(message);
    this.name = 'SceneSelectionError';
    this.code = code;
  }
}

function emptySelection(): SceneSelectionState {
  return Object.freeze({
    selectedSceneopsIds: Object.freeze([]),
    primarySceneopsId: null,
  });
}

function cloneSelection(selection: SceneSelectionState): SceneSelectionState {
  return Object.freeze({
    selectedSceneopsIds: Object.freeze([...selection.selectedSceneopsIds]),
    primarySceneopsId: selection.primarySceneopsId,
  });
}
