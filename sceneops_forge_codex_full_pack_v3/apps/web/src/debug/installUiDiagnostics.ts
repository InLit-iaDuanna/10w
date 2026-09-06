import { recordUiError, recordUiEvent } from './diagnosticState';

let installCount = 0;
let removeListeners: (() => void) | undefined;

/** Installs bounded local global-error capture. Call the returned function on app teardown. */
export function installUiDiagnostics(): () => void {
  installCount += 1;
  if (installCount === 1 && typeof window !== 'undefined') {
    recordUiEvent('page.ready', { phase: 'complete', width: window.innerWidth, height: window.innerHeight });
    const onPageHide = () => recordUiEvent('page.hidden', { phase: 'complete' });
    const onError = (event: ErrorEvent) => {
      recordUiError(event.error instanceof Error ? event.error : event.message, {
        phase: 'error',
        reason: 'window-error',
      });
    };
    const onUnhandledRejection = (event: PromiseRejectionEvent) => {
      recordUiError(event.reason, { phase: 'error', reason: 'unhandled-rejection' });
    };
    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onUnhandledRejection);
    window.addEventListener('pagehide', onPageHide);
    removeListeners = () => {
      window.removeEventListener('error', onError);
      window.removeEventListener('unhandledrejection', onUnhandledRejection);
      window.removeEventListener('pagehide', onPageHide);
    };
  }

  let active = true;
  return () => {
    if (!active) return;
    active = false;
    installCount = Math.max(0, installCount - 1);
    if (installCount === 0) {
      removeListeners?.();
      removeListeners = undefined;
    }
  };
}
