export const UI_DIAGNOSTIC_CAPACITY = 200;
export const UI_DIAGNOSTIC_STORAGE_KEY = 'sceneops.ui-diagnostics.v1';

export type UiDiagnosticEventType = 'page.ready' | 'page.hidden' | 'edge-drag.begin' | 'edge-drag.end' | 'edge-state.changed' | 'editor-load.error' | 'layout-mutation.begin' | 'layout-mutation.end';
export type UiEdge = 'left' | 'right' | 'top' | 'bottom';
export type UiLayoutMode = 'hidden' | 'peek' | 'pinned' | 'drawer' | 'replace' | 'tab' | 'split' | 'floating' | 'popout';
export type UiDiagnosticPhase = 'start' | 'commit' | 'cancel' | 'complete' | 'error';

/** Only non-content layout identifiers and measurements are accepted here. */
export interface UiDiagnosticFields {
  edge?: UiEdge;
  mode?: UiLayoutMode;
  size?: number;
  panelCount?: number;
  instanceId?: string;
  editorId?: string;
  phase?: UiDiagnosticPhase;
  pointerType?: 'mouse' | 'touch' | 'pen' | 'unknown';
  width?: number;
  height?: number;
  reason?: 'window-error' | 'unhandled-rejection' | 'error-boundary' | 'layout-operation';
}

export interface UiDiagnosticEvent {
  timestamp: string;
  type: UiDiagnosticEventType;
  fields: Readonly<UiDiagnosticFields>;
}

export interface UiDiagnosticError {
  timestamp: string;
  type: 'error';
  summary: 'JavaScript error' | 'WebGL context error' | 'Possible memory exhaustion';
  errorName: 'Error' | 'TypeError' | 'RangeError' | 'ReferenceError' | 'SyntaxError' | 'DOMException';
  frames: readonly string[];
  fields: Readonly<UiDiagnosticFields>;
}

export type UiDiagnosticEntry = UiDiagnosticEvent | UiDiagnosticError;
export type UiDiagnosticStorageStatus = 'saved-locally' | 'memory-only';
export interface DiagnosticStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

type DiagnosticListener = () => void;
const IDENTIFIER_LIMIT = 160;
const FRAME_LIMIT = 8;
const allowedEventTypes = new Set<UiDiagnosticEventType>(['page.ready', 'page.hidden', 'edge-drag.begin', 'edge-drag.end', 'edge-state.changed', 'editor-load.error', 'layout-mutation.begin', 'layout-mutation.end']);
const allowedEdges = new Set<UiEdge>(['left', 'right', 'top', 'bottom']);
const allowedModes = new Set<UiLayoutMode>(['hidden', 'peek', 'pinned', 'drawer', 'replace', 'tab', 'split', 'floating', 'popout']);
const allowedPhases = new Set<UiDiagnosticPhase>(['start', 'commit', 'cancel', 'complete', 'error']);
const allowedPointerTypes = new Set<NonNullable<UiDiagnosticFields['pointerType']>>(['mouse', 'touch', 'pen', 'unknown']);
const allowedReasons = new Set<NonNullable<UiDiagnosticFields['reason']>>(['window-error', 'unhandled-rejection', 'error-boundary', 'layout-operation']);
const allowedErrorNames = new Set<UiDiagnosticError['errorName']>(['Error', 'TypeError', 'RangeError', 'ReferenceError', 'SyntaxError', 'DOMException']);
const storedFramePattern = /^\/[a-zA-Z0-9_@./%+-]+\.(?:js|mjs|cjs|ts|tsx):\d+(?::\d+)?$/;

function boundedIdentifier(value: unknown): string | undefined {
  if (typeof value !== 'string' || !/^[a-zA-Z0-9._:-]+$/.test(value)) return undefined;
  return value.slice(0, IDENTIFIER_LIMIT);
}

function boundedMeasurement(value: unknown, maximum: number, integer = false): number | undefined {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > maximum) return undefined;
  return integer ? Math.round(value) : Math.round(value * 100) / 100;
}

export function selectUiDiagnosticFields(fields: UiDiagnosticFields = {}): UiDiagnosticFields {
  const source = fields as Record<string, unknown>;
  const selected: UiDiagnosticFields = {};
  if (allowedEdges.has(source.edge as UiEdge)) selected.edge = source.edge as UiEdge;
  if (allowedModes.has(source.mode as UiLayoutMode)) selected.mode = source.mode as UiLayoutMode;
  if (allowedPhases.has(source.phase as UiDiagnosticPhase)) selected.phase = source.phase as UiDiagnosticPhase;
  if (allowedPointerTypes.has(source.pointerType as NonNullable<UiDiagnosticFields['pointerType']>)) selected.pointerType = source.pointerType as NonNullable<UiDiagnosticFields['pointerType']>;
  if (allowedReasons.has(source.reason as NonNullable<UiDiagnosticFields['reason']>)) selected.reason = source.reason as NonNullable<UiDiagnosticFields['reason']>;
  const size = boundedMeasurement(source.size, 100_000);
  const panelCount = boundedMeasurement(source.panelCount, 1_000, true);
  const width = boundedMeasurement(source.width, 100_000);
  const height = boundedMeasurement(source.height, 100_000);
  const instanceId = boundedIdentifier(source.instanceId);
  const editorId = boundedIdentifier(source.editorId);
  if (size !== undefined) selected.size = size;
  if (panelCount !== undefined) selected.panelCount = panelCount;
  if (width !== undefined) selected.width = width;
  if (height !== undefined) selected.height = height;
  if (instanceId !== undefined) selected.instanceId = instanceId;
  if (editorId !== undefined) selected.editorId = editorId;
  return Object.fromEntries(Object.entries(selected).filter(([, value]) => value !== undefined)) as UiDiagnosticFields;
}

function errorName(value: unknown): UiDiagnosticError['errorName'] {
  const candidate = value instanceof Error ? value.name : '';
  return allowedErrorNames.has(candidate as UiDiagnosticError['errorName']) ? candidate as UiDiagnosticError['errorName'] : 'Error';
}

function errorSummary(value: unknown): UiDiagnosticError['summary'] {
  const message = value instanceof Error ? value.message.toLowerCase() : typeof value === 'string' ? value.toLowerCase() : '';
  if (/out of memory|allocation failed|heap limit/.test(message)) return 'Possible memory exhaustion';
  if (/webgl|context lost/.test(message)) return 'WebGL context error';
  return 'JavaScript error';
}

function extractStackFrames(value: unknown): string[] {
  if (!(value instanceof Error) || typeof value.stack !== 'string') return [];
  const frames: string[] = [];
  const filePattern = /(?:(?:https?|file):\/\/[^/\s)]+)?(\/[a-zA-Z0-9_@./%+-]+?\.(?:js|mjs|cjs|ts|tsx))(?:\?[^)\s]*?)?:(\d+)(?::(\d+))?/i;
  for (const line of value.stack.split('\n')) {
    const match = line.match(filePattern);
    if (!match?.[1]) continue;
    const position = `:${match[2]}${match[3] ? `:${match[3]}` : ''}`;
    frames.push(`${match[1].slice(-300)}${position}`);
    if (frames.length === FRAME_LIMIT) break;
  }
  return frames;
}

export function summarizeUiError(value: unknown): Pick<UiDiagnosticError, 'summary' | 'errorName' | 'frames'> {
  return { summary: errorSummary(value), errorName: errorName(value), frames: extractStackFrames(value) };
}

function isStoredEntry(value: unknown): value is UiDiagnosticEntry {
  if (!value || typeof value !== 'object') return false;
  const entry = value as Record<string, unknown>;
  if (typeof entry.timestamp !== 'string' || Number.isNaN(Date.parse(entry.timestamp))) return false;
  if (entry.type === 'error') {
    return ['JavaScript error', 'WebGL context error', 'Possible memory exhaustion'].includes(String(entry.summary))
      && allowedErrorNames.has(entry.errorName as UiDiagnosticError['errorName'])
      && Array.isArray(entry.frames)
      && entry.frames.length <= FRAME_LIMIT
      && entry.frames.every((frame) => typeof frame === 'string' && storedFramePattern.test(frame))
      && !!entry.fields && typeof entry.fields === 'object';
  }
  return allowedEventTypes.has(entry.type as UiDiagnosticEventType) && !!entry.fields && typeof entry.fields === 'object';
}

export class UiDiagnosticBuffer {
  readonly #capacity: number;
  readonly #storage: DiagnosticStorage | undefined;
  readonly #storageKey: string;
  #entries: UiDiagnosticEntry[] = [];
  #listeners = new Set<DiagnosticListener>();
  #storageStatus: UiDiagnosticStorageStatus;

  constructor(capacity = UI_DIAGNOSTIC_CAPACITY, storage?: DiagnosticStorage, storageKey = UI_DIAGNOSTIC_STORAGE_KEY) {
    if (!Number.isInteger(capacity) || capacity < 1 || capacity > UI_DIAGNOSTIC_CAPACITY) {
      throw new RangeError(`Diagnostic capacity must be between 1 and ${UI_DIAGNOSTIC_CAPACITY}.`);
    }
    this.#capacity = capacity;
    this.#storage = storage;
    this.#storageKey = storageKey;
    this.#storageStatus = storage ? 'saved-locally' : 'memory-only';
    this.#restore();
  }

  record(type: UiDiagnosticEventType, fields: UiDiagnosticFields = {}): void {
    if (!allowedEventTypes.has(type)) return;
    this.#append({ timestamp: new Date().toISOString(), type, fields: selectUiDiagnosticFields(fields) });
  }

  recordError(value: unknown, fields: UiDiagnosticFields = {}): void {
    this.#append({ timestamp: new Date().toISOString(), type: 'error', ...summarizeUiError(value), fields: selectUiDiagnosticFields(fields) });
  }

  snapshot(): readonly UiDiagnosticEntry[] { return this.#entries; }
  storageStatus(): UiDiagnosticStorageStatus { return this.#storageStatus; }

  clear(): void {
    this.#entries = [];
    try { this.#storage?.removeItem(this.#storageKey); }
    catch { this.#storageStatus = 'memory-only'; }
    this.#notify();
  }

  subscribe(listener: DiagnosticListener): () => void {
    this.#listeners.add(listener);
    return () => this.#listeners.delete(listener);
  }

  #restore(): void {
    if (!this.#storage) return;
    try {
      const raw = this.#storage.getItem(this.#storageKey);
      if (!raw) return;
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed)) this.#entries = parsed.filter(isStoredEntry).slice(-this.#capacity).map((entry) => Object.freeze({ ...entry, fields: selectUiDiagnosticFields(entry.fields) }));
    } catch {
      this.#entries = [];
      this.#storageStatus = 'memory-only';
    }
  }

  #append(entry: UiDiagnosticEntry): void {
    this.#entries = [...this.#entries.slice(-(this.#capacity - 1)), Object.freeze(entry)];
    try { this.#storage?.setItem(this.#storageKey, JSON.stringify(this.#entries)); }
    catch { this.#storageStatus = 'memory-only'; }
    this.#notify();
  }

  #notify(): void { for (const listener of this.#listeners) listener(); }
}

function browserStorage(): DiagnosticStorage | undefined {
  if (typeof window === 'undefined') return undefined;
  try { return window.localStorage; }
  catch { return undefined; }
}

export const uiDiagnosticBuffer = new UiDiagnosticBuffer(UI_DIAGNOSTIC_CAPACITY, browserStorage());

function forwardUiDiagnostic(entry: UiDiagnosticEntry): void {
  if (typeof window === 'undefined' || typeof fetch !== 'function') return;
  void fetch('/api/audit/ui-events', {
    method: 'POST',
    headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
    keepalive: true,
  }).catch(() => undefined);
}

export function recordUiEvent(type: UiDiagnosticEventType, fields: UiDiagnosticFields = {}): void {
  uiDiagnosticBuffer.record(type, fields);
  const entry: UiDiagnosticEvent = { timestamp: new Date().toISOString(), type, fields: selectUiDiagnosticFields(fields) };
  forwardUiDiagnostic(entry);
}

export function recordUiError(value: unknown, fields: UiDiagnosticFields = {}): void {
  uiDiagnosticBuffer.recordError(value, fields);
  const entry: UiDiagnosticError = { timestamp: new Date().toISOString(), type: 'error', ...summarizeUiError(value), fields: selectUiDiagnosticFields(fields) };
  forwardUiDiagnostic(entry);
}
