import {useEffect, useId, useRef, useState, type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import './composer-menu.css';

type Option = {value:string;label:string;description?:string;icon?:ReactNode};
export function ComposerMenu({label,value,options,onChange,disabled=false,icon}: {
  label:string;value:string;options:Option[];onChange:(value:string)=>void;disabled?:boolean;icon?:ReactNode;
}) {
  const [position,setPosition] = useState<{left:number;bottom:number}|null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const id=useId();
  const selected=options.find(option=>option.value===value);
  const close=()=>{setPosition(null);trigger.current?.focus();};
  const open=()=>{
    if(position){close();return;}
    const rect=trigger.current!.getBoundingClientRect();
    setPosition({left:Math.max(12,Math.min(rect.left,window.innerWidth-292)),bottom:window.innerHeight-rect.top+8});
  };
  useEffect(()=>{
    if(!position)return;
    const active=menu.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]') ?? menu.current?.querySelector<HTMLButtonElement>('button');
    active?.focus();
    const outside=(event:PointerEvent)=>{if(!menu.current?.contains(event.target as Node)&&!trigger.current?.contains(event.target as Node))setPosition(null);};
    const resize=()=>setPosition(null);
    document.addEventListener('pointerdown',outside);window.addEventListener('resize',resize);
    return()=>{document.removeEventListener('pointerdown',outside);window.removeEventListener('resize',resize);};
  },[position]);
  useEffect(()=>{if(disabled)setPosition(null);},[disabled]);
  return <><button ref={trigger} type="button" className="composer-menu-trigger" aria-label={label} aria-haspopup="menu" aria-expanded={!!position} aria-controls={position?id:undefined} disabled={disabled} onClick={open} onKeyDown={event=>{if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();open();}}}>
    {icon ?? selected?.icon}<span>{selected?.label ?? value}</span><svg className="composer-menu-chevron" aria-hidden="true" viewBox="0 0 16 16"><path d="m4 6 4 4 4-4"/></svg>
  </button>{position && createPortal(<div ref={menu} id={id} className="composer-menu-popup" role="menu" aria-label={label} style={position} onKeyDown={event=>{
    const buttons=Array.from(menu.current!.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]'));
    const index=buttons.indexOf(document.activeElement as HTMLButtonElement);
    if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
      event.preventDefault();buttons[event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus();
    }else if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close();}
    else if(event.key==='Tab')setPosition(null);
  }}><div className="composer-menu-heading">{label}</div>{options.map(option=><button key={option.value} role="menuitemradio" aria-checked={option.value===value} tabIndex={-1} type="button" onClick={()=>{onChange(option.value);close();}}>
    {option.icon}<span className="composer-menu-option-copy"><strong>{option.label}</strong>{option.description&&<small>{option.description}</small>}</span>
    <svg className="composer-menu-check" aria-hidden="true" viewBox="0 0 16 16" style={{visibility:option.value===value?'visible':'hidden'}}><path d="m3 8 3 3 7-7"/></svg>
  </button>)}</div>,document.body)}</>;
}
