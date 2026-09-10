export function EnvironmentToolIcon({kind}:{kind:'cube'|'plus'|'library'|'upload'}) {
 return <svg className="environment-tool-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{kind==='cube'?<><path d="m12 3 9 5v9l-9 5-9-5V8Zm-9 5 9 5 9-5M12 13v9"/></>:kind==='plus'?<path d="M12 5v14M5 12h14"/>:kind==='upload'?<><path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/></>:<><path d="M4 3v18h17M8 4v13m4-12v12m4-13 4 12"/></>}</svg>;
}
