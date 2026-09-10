import { useEffect, useRef, useState } from 'react';
import { MarkdownMessage } from './MarkdownMessage';

/** A host-bound editing target in the existing project conversation. */
export interface DomainConversationPort {
  projectId: string;
  label: string;
  lighting: boolean;
  setLighting(value: boolean): void;
  history?(signal?:AbortSignal):Promise<Array<{id:string;prompt:string;target:{asset_id:string};summary:string;status:string;created_at?:string}>>;
  submit(text: string, signal: AbortSignal, turnId?:string): Promise<{summary: string;status?:'applied'|'declined'|'noop';turnId?:string;createdAt?:string}>;
  clear(): void;
}

type Turn = {id:string; text:string; target:string; summary:string; createdAt:string; status:'pending'|'applied'|'failed'|'cancelled'|'declined'|'noop'};
export function useDomainConversation(port?: DomainConversationPort | null, readHistory?: DomainConversationPort['history']) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [pending, setPending] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(()=>{
    const read=readHistory??port?.history;
    if(!read) return;
    const controller=new AbortController();
    void read(controller.signal).then(records=>setTurns(current=>{
      const byId=new Map(records.map(record=>[record.id,{id:record.id,text:record.prompt,target:record.target.asset_id,
        summary:record.summary,createdAt:record.created_at??'',status:(record.status==='proposed'?'pending':record.status) as Turn['status']} ]));
      for(const turn of current) if(!byId.has(turn.id)||turn.status==='pending') byId.set(turn.id,turn);
      return [...byId.values()].sort((a,b)=>a.createdAt.localeCompare(b.createdAt));
    })).catch(error=>{if(!controller.signal.aborted) setHistoryError(error instanceof Error?error.message:String(error));});
    return()=>controller.abort();
  },[port?.projectId,readHistory]);
  const [historyError,setHistoryError]=useState('');
  useEffect(() => () => request.current?.abort(), []);
  async function submit(text: string) {
    if (!port || request.current) return;
    const fixed = port;
    const controller = new AbortController();
    const id = crypto.randomUUID();
    request.current = controller;
    setPending(true);
    setTurns(current => [...current, {id,text,target:fixed.label,summary:'正在调整材质…',createdAt:new Date().toISOString(),status:'pending'}]);
    try {
      const result = await fixed.submit(text, controller.signal,id);
      controller.signal.throwIfAborted();
      setTurns(current => current.map(turn => turn.id === id ? {...turn,id:result.turnId??turn.id,createdAt:result.createdAt??turn.createdAt,summary:result.summary,status:result.status??'applied'} : turn));
    } catch (error) {
      setTurns(current => current.map(turn => turn.id === id ? {...turn,
        summary:controller.signal.aborted ? '已停止本次材质调整。' : error instanceof Error ? error.message : String(error),
        status:controller.signal.aborted ? 'cancelled' : 'failed'} : turn));
    } finally {
      if (request.current === controller) {request.current = null; setPending(false);}
    }
  }
  return {pending,submit,historyError,cancel:()=>request.current?.abort(),turns};
}

export function DomainConversationTarget({port,disabled=false}:{port:DomainConversationPort;disabled?:boolean}) {
  return <div className="sceneops-domain-target"><span>材质 · {port.label}</span>
    <label><input type="checkbox" checked={port.lighting} disabled={disabled}
      onChange={event=>port.setLighting(event.target.checked)}/>同时调整灯光与环境</label>
    <button type="button" disabled={disabled} onClick={port.clear} aria-label="清除材质目标">×</button></div>;
}
export function DomainConversationTurns({turns,className='journey-message'}:{turns:Turn[];className?:string}) {
  return <>{turns.map(turn=><div key={turn.id}>
    <article className={`${className} user`}><small>你 · {turn.target}</small><MarkdownMessage text={turn.text}/></article>
    <article className={`${className} assistant`} role={turn.status==='failed'?'alert':'status'}>
      <small>材质与灯光 · {turn.status==='pending'?'处理中':turn.status==='applied'?'已应用到编辑预览':turn.status==='cancelled'?'已停止':turn.status==='noop'?'无需修改':turn.status==='declined'?'未执行':'未应用'}</small>
      <MarkdownMessage text={turn.summary}/></article>
  </div>)}</>;
}
