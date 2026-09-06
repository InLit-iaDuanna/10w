export const UI_DIAGNOSTIC_CAPACITY = 250;

export type UiEdge = 'left' | 'right' | 'top' | 'bottom';
export type UiLayoutMode = 'hidden' | 'peek' | 'pinned' | 'drawer' | 'replace' | 'tab' | 'split' | 'floating' | 'popout';
export type UiDiagnosticPhase = 'start' | 'preview' | 'commit' | 'cancel' | 'complete' | 'error';

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
  type: string;
  fields: Readonly<UiDiagnosticFields>;
}

export interface UiDiagnosticError {
  timestamp: string;
  type: 'error';
  summary: string;
  stack?: string;
  fields: Readonly<UiDiagnosticFields>;
}

export type UiDiagnosticEntry = UiDiagnosticEvent | UiDiagnosticError;
type DiagnosticListener = () => void;

const STRING_LIMIT = 160;
const SUMMARY_LIMIT = 500;
const STACK_LIMIT = 2_000;
const STACK_LINE_LIMIT = 8;
const eventTypePattern = /^[a-z][a-z0-9.-]{0,79}$/;
const allowedEdges = new Set<UiEdge>(['left', 'right', 'top', 'bottom']);
const allowedModes = new Set<UiLayoutMode>(['hidden', 'peek', 'pinned', 'drawer', 'replace', 'tab', 'split', 'floating', 'popout']);
const allowedPhases = new Set<UiDiagnosticPhase>(['start', 'preview', 'commit', 'cancel', 'complete', 'error']);
const allowedPointerTypes = new Set<NonNullable<UiDiagnosticFields['pointerType']>>(['mouse', 'touch', 'pen', 'unknown']);
const allowedReasons = new Set<NonNullable<UiDiagnosticFields['reason']>>(['window-error', 'unhandled-rejection', 'error-boundary', 'layout-operation']);

function boundedString(value: unknown, limit = STRING_LIMIT): string | undefined {
  if (typeof value !== 'string') return undefined;
  const normalized = value.replace(/[\u0000-\u001f\u007f]/g, ' ').trim();
  return normalized ? normalized.slice(0, limit) : undefined;
}

function finiteNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

export function selectUiDiagnosticFields(fields: UiDiagnosticFields = {}): UiDiagnosticFields {
  const source = fields as Record<string, unknown>;
  const selected: UiDiagnosticFields = {};
  if (allowedEdges.has(source.edge as UiEdge)) selected.edge = source.edge as UiEdge;
  if (allowedModes.has(source.mode as UiLayoutMode)) selected.mode = source.mode as UiLayoutMode;
  if (allowedPhases.has(source.phase as UiDiagnosticPhase)) selected.phase = source.phase as UiDiagnosticPhase;
  if (allowedPointerTypes.has(source.pointerType as NonNullable<UiDiagnosticFields['pointerType']>)) selected.pointerType = source.pointerType as NonNullable<UiDiagnosticFields['pointerType']>;
  if (allowedReasons.has(source.reason as NonNullable<UiDiagnosticFields['reason']>)) selected.reason = source.reason as NonNullable<UiDiagnosticFields['reason']>;
  selected.size = finiteNumber(source.size);
  selected.panelCount = finiteNumber(source.panelCount);
  selected.width = finiteNumber(source.width);
  selected.height = finiteNumber(source.height);
  selected.instanceId = boundedString(source.instanceId);
  selected.editorId = boundedString(source.editorId);
  return Object.fromEntries(Object.entries(selected).filter(([, value]) => value !== undefined)) as UiDiagnosticFields;
}

function removeUrlDetails(value: string): string {
  return value.replace(/https?:\/\/[^\s)\]}]+/gi, (match) => {
    try {
      const url = new URL(match);
      return `${url.origin}${url.pathname}`;
    } catch {
      return match.replace(/[?#].*$/, '');
    }
  });
}

function sanitizeErrorText(value: string, limit: number): string {
  return removeUrlDetails(value)
    .replace(/\b(?:authorization|cookie|set-cookie|x-api-key)\s*[:=]\s*[^\s,;]+/gi, '$1=[redacted]')
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, '')
    .trim()
    .slice(0, limit);
}

export function summarizeUiError(value: unknown): { summary: string; stack?: string } {
  if (value instanceof Error) {
    const name = boundedString(value.name, 80) ?? 'Error';
    const message = sanitizeErrorText(value.message || 'No message', SUMMARY_LIMIT);
    const stack = typeof value.stack === 'string'
      ? sanitizeErrorText(value.stack.split('\n').slice(0, STACK_LINE_LIMIT).join('\n'), STACK_LIMIT)
      : '';
    return { summary: `${name}: ${message}`.slice(0, SUMMARY_LIMIT), ...(stack ? { stack } : {}) };
  }
  if (typeof value === 'string') return { summary: sanitizeErrorText(value, SUMMARY_LIMIT) || 'Unhandled error' };
  return { summary: `Unhandled ${value === null ? 'null' : typeof value} error value` };
}

export class UiDiagnosticBuffer {
  readonly #capacity: number;
  #entries: UiDiagnosticEntry[] = [];
  #listeners = new Set<DiagnosticListener>();

  constructor(capacity = UI_DIAGNOSTIC_CAPACITY) {
    if (!Number.isInteger(capacity) || capacity < 1) throw new RangeError('Diagnostic capacity must be a positive integer.');
    this.#capacity = capacity;
  }

  record(type: string, fields: UiDiagnosticFields = {}): void {
    const safeType = eventTypePattern.test(type) ? type : 'ui.invalid-event-type';
    this.#append({ timestamp: new Date().toISOString(), type: safeType, fields: selectUiDiagnosticFields(fields) });
  }

  recordError(value: unknown, fields: UiDiagnosticFields = {}): void {
    this.#append({ timestamp: new Date().toISOString(), type: 'error', ...summarizeUiError(value), fields: selectUiDiagnosticFields(fields) });
  }

  snapshot(): readonly UiDiagnosticEntry[] {
    return this.#entries;
  }

  clear(): void {
    if (!this.#entries.length) return;
    this.#entries = [];
    this.#notify();
  }

  subscribe(listener: DiagnosticListener): () => void {
    this.#listeners.add(listener);
    return () => this.#listeners.delete(listener);
  }

  #append(entry: UiDiagnosticEntry): void {
    this.#entries = [...this.#entries.slice(-(this.#capacity - 1)), Object.freeze(entry)];
    this.#notify();
  }

  #notify(): void {
    for (const listener of this.#listeners) listener();
  }
}

export const uiDiagnosticBuffer = new UiDiagnosticBuffer();

export function recordUiEvent(type: string, fields: UiDiagnosticFields = {}): void {
  uiDiagnosticBuffer.record(type, fields);
}

export function recordUiError(value: unknown, fields: UiDiagnosticFields = {}): void {
  uiDiagnosticBuffer.recordError(value, fields);
}
