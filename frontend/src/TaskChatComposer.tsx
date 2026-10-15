import React,{useEffect,useId,useRef,useState} from 'react';
import {workRequest} from './workApi';

export function TaskChatComposer({taskId,value,onChange,mentions,onMentions,busy,onSend}:{taskId:string;value:string;onChange:(s:string)=>void;mentions:string[];onMentions:(ids:string[])=>void;busy:boolean;onSend:()=>Promise<void>}) {
  const input=useRef<HTMLTextAreaElement>(null);
  const [caret,setCaret]=useState(0),[choices,setChoices]=useState<any[]>([]),[active,setActive]=useState(0),[dismissed,setDismissed]=useState(false),[error,setError]=useState('');
  const chosen=useRef<Record<string,string>>({});const listId=useId();
  const match=value.slice(0,caret).match(/(?:^|\s)@([^@\n]{0,80})$/);
  const query=match?.[1];const open=query!==undefined&&!dismissed;
  useEffect(()=>{let current=true;setChoices([]);setActive(0);setError('');if(!open)return;
    const timer=window.setTimeout(()=>workRequest<any>(`/tasks/${taskId}/participant-options/?search=${encodeURIComponent(query||'')}`).then(x=>{if(current)setChoices(x.results);}).catch(e=>{if(current)setError(e.message);}),200);
    return()=>{current=false;window.clearTimeout(timer);};
  },[taskId,query,open]);
  useEffect(()=>{if(!value){chosen.current={};setCaret(0);}},[value]);
  const change=(next:string)=>{onChange(next);onMentions(mentions.filter(id=>chosen.current[id]&&next.includes('@'+chosen.current[id])));setDismissed(false);};
  const select=(person:any)=>{const start=caret-(query?.length||0)-1;const text=value.slice(0,start)+'@'+person.name+' '+value.slice(caret);chosen.current[person.id]=person.name;onMentions([...new Set([...mentions,person.id])]);onChange(text);setDismissed(true);const position=start+person.name.length+2;requestAnimationFrame(()=>{input.current?.focus();input.current?.setSelectionRange(position,position);setCaret(position);});};
  return <form className="comment-form task-chat-composer" onSubmit={e=>{e.preventDefault();void onSend();}}>
    <div className="task-chat-input"><textarea ref={input} aria-label="Новый комментарий" aria-controls={open?listId:undefined} aria-activedescendant={open&&choices[active]?`${listId}-${active}`:undefined} value={value} disabled={busy} onChange={e=>{change(e.target.value);setCaret(e.target.selectionStart);}} onSelect={e=>setCaret(e.currentTarget.selectionStart)} placeholder="Сообщение… @ — упомянуть сотрудника" onKeyDown={e=>{
      if(e.key==='Escape'){setDismissed(true);return;}
      if(open&&choices.length){if(e.key==='ArrowDown'){e.preventDefault();setActive(i=>Math.min(i+1,choices.length-1));}if(e.key==='ArrowUp'){e.preventDefault();setActive(i=>Math.max(i-1,0));}if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();select(choices[active]);}}
    }}/>
    {open&&<div className="task-chat-mentions" id={listId} role="listbox" aria-label="Упомянуть сотрудника">{choices.map((p,i)=><button id={`${listId}-${i}`} type="button" role="option" aria-selected={i===active} key={p.id} onMouseDown={e=>e.preventDefault()} onClick={()=>select(p)}>{p.name}{!p.has_access&&<small>Нет доступа к задаче</small>}</button>)}{error&&<p role="alert">{error}</p>}</div>}
    </div><button disabled={busy||!value.trim()}>Отправить</button>
  </form>;
}
