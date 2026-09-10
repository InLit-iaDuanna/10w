export function JourneyComposerIcon({kind}:{kind:'send'|'stop'|'shield'}) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    {kind === 'send' ? <path d="M12 19V5m-6 6 6-6 6 6" /> : kind === 'stop' ? <rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none" />
      : <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z" /><path d="m8 12 3 3 5-6" /></>}
  </svg>;
}
