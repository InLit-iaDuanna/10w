import { validateAnnotation } from './annotations.ts';
import type {
  AnnotationContext,
  WorldAnnotation,
  WorldExecutionMode,
} from './contracts.ts';

export type VoiceTranscriptSource =
  | {
      state: 'ready';
      transcript: string;
      locale: string;
      confidence: number | null;
      audioEvidenceId: string;
      mode: WorldExecutionMode;
    }
  | {
      state: 'blocked';
      reason: string;
    };

export type VoiceDraftOutcome =
  | { state: 'created'; mode: WorldExecutionMode; annotation: WorldAnnotation }
  | { state: 'blocked'; mode: 'blocked'; reason: string };

export function createVoiceDraftAnnotation(
  annotationId: string,
  context: Omit<AnnotationContext, 'mode'>,
  source: VoiceTranscriptSource,
): VoiceDraftOutcome {
  if (source.state === 'blocked') {
    if (!source.reason.trim()) throw new Error('Blocked voice transcription requires a reason');
    return { state: 'blocked', mode: 'blocked', reason: source.reason };
  }
  const annotation: WorldAnnotation = {
    schemaVersion: 1,
    annotationId,
    type: 'voice-draft',
    status: 'draft',
    context: { ...structuredClone(context), mode: source.mode },
    details: {
      kind: 'voice-draft',
      transcript: source.transcript,
      locale: source.locale,
      transcriptionConfidence: source.confidence,
      audioEvidenceId: source.audioEvidenceId,
      draft: true,
    },
  };
  validateAnnotation(annotation);
  return { state: 'created', mode: source.mode, annotation };
}
