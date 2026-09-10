/** Shared 24px line icons for the tool catalog. Labels stay in the tool button. */
export function ToolLibraryIcon({ name }: { name: string }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    {name === 'library' ? <>
      <path d="M3 4v16h18M7 4v12M11 6v10M15 4l4 11M6 17h14" />
      <path d="M7 7h1M11 9h1M16 7l2-.6" />
    </> : name === 'git-branch' ? <>
      <circle cx="6" cy="5" r="2.5" /><circle cx="6" cy="19" r="2.5" /><circle cx="18" cy="6" r="2.5" />
      <path d="M6 7.5v9M18 8.5v1a5 5 0 0 1-5 5H6" />
    </> : name === 'cube' ? <>
      <path d="m12 2 9 5v10l-9 5-9-5V7l9-5Zm-9 5 9 5 9-5M12 12v10M7.5 4.5l9 5" />
    </> : name === 'landscape' ? <>
      <path d="m2 19 6-10 4 6 3-4 7 8H2ZM6 12l2 2 2-2" /><circle cx="16" cy="5" r="2" />
    </> : name === 'code' ? <path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-14-2 18"/> : name === 'play' ? <><rect x="3" y="3" width="18" height="18" rx="4"/><path d="m10 8 6 4-6 4Z"/></> : name === 'plan' ? <><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8m-8 4h5"/></> : name === 'activity' ? <><path d="M3 17h3l3-10 5 14 3-10h4M3 3v18h18"/></> : <>
      <rect x="3" y="3" width="18" height="18" rx="3" /><path d="M3 9h18M9 9v12" />
    </>}
  </svg>;
}
