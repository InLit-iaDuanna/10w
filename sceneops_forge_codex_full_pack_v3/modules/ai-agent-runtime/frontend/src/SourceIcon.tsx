import type { ReactNode } from 'react';
const shapes: Record<string, ReactNode> = {
 code:<><path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16"/></>,
 folder:<path d="M3 7V5a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v12H3Z"/>,
 file:<><path d="M14 3H5v18h14V8Zm0 0v5h5M8 12h8m-8 4h5"/></>,
 search:<><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
 close:<path d="m6 6 12 12M6 18 18 6"/>,
 chevron:<path d="m9 5 7 7-7 7"/>,
 branch:<><circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="6" r="2"/><path d="M6 7v10m0-4h5a7 7 0 0 0 7-5"/></>,
 save:<><path d="M4 3h13l3 3v15H4Zm3 0v6h9V3M8 21v-8h8v8"/></>,
 refresh:<><path d="M20 10a8 8 0 1 0-1 7M20 4v6h-6"/></>,
 spark:<><path d="m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6ZM20 2v4m-2-2h4"/></>,
 arrow:<path d="M4 12h16m-6-6 6 6-6 6"/>,
 shield:<><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/></>,
 check:<path d="m5 12 4 4L19 6"/>,
 undo:<><path d="m8 4-5 5 5 5M3 9h10a7 7 0 0 1 0 14"/></>,
};
export function SourceIcon({name, className=''}:{name:keyof typeof shapes;className?:string}) {
 return <svg className={`source-icon ${className}`} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>;
}
