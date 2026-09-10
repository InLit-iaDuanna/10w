import { useEffect, useState } from 'react';
/** Only navigate when the cited saved message is present in this transcript. */
export function MemorySource({source}:{source:string}) {
  const messageId=source.includes(':message:')?source.split(':message:').at(-1):source.startsWith('message:')?source.slice(8):null;
  const targetId=messageId?`memory-message-${messageId}`:null;
  const [available,setAvailable]=useState(false);
  useEffect(()=>{setAvailable(!!targetId && !!document.getElementById(targetId));},[targetId]);
  return available?<button type="button" onClick={()=>{const target=targetId?document.getElementById(targetId):null;if(!target){setAvailable(false);return;}target.scrollIntoView({block:'center',behavior:'smooth'});target.setAttribute('tabindex','-1');target.focus({preventScroll:true});}}>查看来源消息</button>:<small>{source}</small>;
}
