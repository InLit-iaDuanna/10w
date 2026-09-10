export function ProviderSettingsIcon({kind}:{kind:'connection'|'preferences'|'check'|'models'}) {
 return <svg className="provider-settings-icon" aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
  {kind==='connection' ? <><path d="m9 15 6-6m-7 3-2 2a4 4 0 0 0 6 6l2-2M10 6l2-2a4 4 0 0 1 6 6l-2 2"/></>
   : kind==='preferences' ? <><path d="M4 7h8m4 0h4M4 17h3m4 0h9"/><circle cx="14" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></>
   : kind==='models' ? <><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 9h6v6H9ZM9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3"/></>
   : <path d="m5 12 4 4L19 6"/>}
 </svg>;
}
