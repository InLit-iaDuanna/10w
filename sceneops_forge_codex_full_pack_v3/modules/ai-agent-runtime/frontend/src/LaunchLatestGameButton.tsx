import {useEffect, useRef, useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {launchLatestGame} from './launchLatestGame';

export function LaunchLatestGameButton({projectId,onOpen}: {
  projectId:string|null; onOpen:(projectId:string,taskId:string)=>Promise<unknown>;
}) {
  const cache=useQueryClient();
  const busy=useRef(false);
  const [pending,setPending]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>setError(''),[projectId]);
  async function launch() {
    if(!projectId || busy.current)return;
    busy.current=true; setPending(true); setError('');
    try {
      const taskId=await launchLatestGame(projectId);
      await cache.invalidateQueries({queryKey:['agent-tasks']});
      await onOpen(projectId,taskId);
    } catch(error) {setError(error instanceof Error?error.message:String(error));}
    finally {busy.current=false;setPending(false);}
  }
  useEffect(()=>{
    const keydown=(event:KeyboardEvent)=>{
      if(event.code==='KeyP' && (event.metaKey||event.ctrlKey) && event.altKey && !event.shiftKey && !event.repeat) {
        event.preventDefault(); void launch();
      }
    };
    window.addEventListener('keydown',keydown);
    return ()=>window.removeEventListener('keydown',keydown);
  },[projectId,onOpen]);
  return <><button disabled={!projectId||pending} onClick={()=>void launch()}
    title="启动当前项目最新游戏 · ⌘/Ctrl + Alt + P" aria-keyshortcuts="Meta+Alt+P Control+Alt+P">
    {pending?'启动中…':'启动游戏'}</button>{error&&<span role="alert">{error}</span>}</>;
}
