export type OutgoingStatus = 'pending' | 'failed' | 'cancelled';

export type CancellationCause = 'user' | 'context_changed' | 'request_aborted';

export type OutgoingAttempt = {
  id: string;
  text: string;
  createdAt: string;
  status: OutgoingStatus;
  attemptNumber: number;
  error?: string;
  cancellationCause?: CancellationCause;
  responseText?: string;
  streamStatus?: string;
};

export type OutgoingEvent =
  | { type: 'started'; attempt: OutgoingAttempt }
  | { type: 'failed'; attemptId: string; error: string }
  | { type: 'cancelled'; attemptId: string; cause: CancellationCause }
  | { type: 'retried'; attemptId: string }
  | { type: 'response_delta'; attemptId: string; text: string }
  | { type: 'response_status'; attemptId: string; text: string }
  | { type: 'saved'; attemptId: string };

export function createOutgoingAttempt(id: string, text: string, createdAt: string): OutgoingAttempt {
  return { id, text, createdAt, status: 'pending', attemptNumber: 1 };
}

export function outgoingConversationReducer(
  attempts: OutgoingAttempt[],
  event: OutgoingEvent,
): OutgoingAttempt[] {
  if (event.type === 'started') return [...attempts, event.attempt];
  if (event.type === 'saved') return attempts.filter(attempt => attempt.id !== event.attemptId);

  return attempts.map(attempt => {
    if (attempt.id !== event.attemptId) return attempt;
    if (event.type === 'response_delta') {
      return { ...attempt, responseText: (attempt.responseText ?? '') + event.text };
    }
    if (event.type === 'response_status') {
      return { ...attempt, streamStatus: event.text };
    }
    const next = { ...attempt };
    delete next.error;
    delete next.cancellationCause;
    if (event.type === 'failed') {
      return { ...next, status: 'failed', error: event.error };
    }
    if (event.type === 'retried') {
      delete next.responseText;
      delete next.streamStatus;
      return {
        ...next,
        status: 'pending',
        attemptNumber: attempt.attemptNumber + 1,
      };
    }
    if (attempt.status === 'cancelled') return attempt;
    return { ...next, status: 'cancelled', cancellationCause: event.cause };
  });
}

export function hasPendingAttempt(attempts: OutgoingAttempt[]): boolean {
  return attempts.some(attempt => attempt.status === 'pending');
}
