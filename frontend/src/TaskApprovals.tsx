import React,{useEffect,useRef,useState} from 'react';
import {workRequest,WorkApiError} from './workApi';

type Event={id:string;sequence:number;round_number:number;action:string;actor_display:string;text:string;created_at:string};
type Approval={id:string;comment:string;approver:string;requester_display:string;approver_display:string;status:string;round_number:number;version:number;source_body:string;history:Event[];available_actions:string[]};
const statusLabels:Record<string,string>={PENDING:'Ожидает согласования',CLARIFICATION_REQUESTED:'Нужно уточнение',APPROVED:'Согласовано',CANCELLED:'Отменено'};
const actionLabels:Record<string,string>={request:'Запросить согласование',approve:'Согласовано',clarify:'Запросить уточнение',resubmit:'Отправить новый раунд',cancel:'Отменить согласование'};
const eventLabels:Record<string,string>={request:'Запрос согласования',approve:'Согласовано',clarify:'Запрошено уточнение',resubmit:'Новый раунд',cancel:'Отменено'};
const message=(e:unknown)=>e instanceof Error?e.message:'Не удалось выполнить действие.';

export function useTaskApprovals(taskId:string){
  const [items,setItems]=useState<Approval[]>([]),[error,setError]=useState('');
  const refresh=async()=>{try{const result=await workRequest<Approval[]>(`/tasks/${taskId}/approvals/`);setItems(Array.isArray(result)?result:[]);setError('');}catch(e){if(e instanceof WorkApiError&&e.status===403){setItems([]);setError('');}else setError(message(e));}};
  useEffect(()=>{void refresh();},[taskId]);
  return {items,error,refresh};
}

function useCommand(){
  const pending=useRef({signature:'',id:''});
  return (signature:string)=>{if(pending.current.signature!==signature)pending.current={signature,id:crypto.randomUUID()};return pending.current.id;};
}

function ApprovalCard({taskId,approval,reload}:{taskId:string;approval:Approval;reload:()=>Promise<void>}){
  const [action,setAction]=useState(''),[text,setText]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');const command=useCommand();
  const submit=async(e:React.FormEvent)=>{e.preventDefault();if(!text.trim()||busy)return;setBusy(true);setError('');const body={text:text.trim(),version:approval.version};const command_id=command(JSON.stringify([approval.id,action,body]));try{await workRequest(`/tasks/${taskId}/approvals/${approval.id}/${action}/`,{method:'POST',body:JSON.stringify({...body,command_id})});setAction('');setText('');await reload();}catch(e){setError(message(e));if(e instanceof WorkApiError&&e.status===409)await reload();}finally{setBusy(false);}};
  return <section className="task-approval" aria-label={`Согласование: ${approval.approver_display}`}>
    <header><strong>{approval.approver_display}</strong><span className={`approval-status ${approval.status.toLowerCase()}`}>{statusLabels[approval.status]||approval.status}</span></header>
    <small>Раунд {approval.round_number} · инициатор: {approval.requester_display}</small>
    {approval.history.length>0&&<p className="approval-latest">{approval.history[approval.history.length-1].text}</p>}
    <details><summary>История согласования · {approval.history.length}</summary><blockquote>{approval.source_body}</blockquote><ol>{approval.history.map(event=><li key={event.id}><b>{eventLabels[event.action]} · раунд {event.round_number}</b><small>{event.actor_display} · {new Date(event.created_at).toLocaleString('ru-RU')}</small><p>{event.text}</p></li>)}</ol></details>
    {!action&&<div className="approval-actions">{approval.available_actions.map(name=><button key={name} type="button" disabled={busy} onClick={()=>{setAction(name);setText('');setError('');}}>{actionLabels[name]}</button>)}</div>}
    {action&&<form className="approval-form" onSubmit={submit}><label>{actionLabels[action]} — комментарий обязателен<textarea required maxLength={10000} value={text} disabled={busy} onChange={e=>setText(e.target.value)}/></label><div><button type="button" disabled={busy} onClick={()=>setAction('')}>Отмена</button><button disabled={busy||!text.trim()}>{busy?'Сохранение…':'Подтвердить'}</button></div></form>}
    {error&&<p role="alert">{error}</p>}
  </section>;
}

export function CommentApprovals({taskId,comment,approvals,reload}:{taskId:string;comment:any;approvals:Approval[];reload:()=>Promise<void>}){
  return <div className="comment-approvals">{approvals.map(a=><details className="chat-approval-chip" key={a.id}><summary><span className={`approval-status ${a.status.toLowerCase()}`}>{statusLabels[a.status]||a.status}</span><span>{a.approver_display}</span></summary><ApprovalCard taskId={taskId} approval={a} reload={reload}/></details>)}</div>;
}

function ApprovalRequestForm({taskId,comment,approvals,reload,onClose}:{taskId:string;comment:any;approvals:Approval[];reload:()=>Promise<void>;onClose:()=>void}){
  const [people,setPeople]=useState<{id:string;name:string}[]>([]),[selected,setSelected]=useState(''),[text,setText]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true);const command=useCommand();
  useEffect(()=>{let active=true;workRequest<{id:string;name:string}[]>(`/tasks/${taskId}/comments/${comment.id}/approval-options/`).then(p=>{if(active)setPeople(p)}).catch(e=>{if(active)setError(message(e))}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[taskId,comment.id]);
  const submit=async(e:React.FormEvent)=>{e.preventDefault();if(!selected||!text.trim()||busy||loading)return;setBusy(true);setError('');const body={comment:comment.id,approver:selected,text:text.trim()};const command_id=command(JSON.stringify(body));try{await workRequest(`/tasks/${taskId}/approvals/`,{method:'POST',body:JSON.stringify({...body,command_id})});await reload();onClose()}catch(e){setError(message(e));if(e instanceof WorkApiError&&e.status===409)await reload()}finally{setBusy(false)}};
  return <form className="approval-form" onSubmit={submit}>
    <label>Согласующий<select required autoFocus value={selected} disabled={busy||loading} onChange={e=>setSelected(e.target.value)}><option value="">{loading?'Загрузка…':'Выберите сотрудника'}</option>{people.map(p=><option key={p.id} value={p.id} disabled={approvals.some(a=>a.approver===p.id)}>{p.name}{approvals.some(a=>a.approver===p.id)?' — запрос уже создан':''}</option>)}</select></label>
    {!loading&&!people.length&&!error&&<p className="muted">Нет сотрудников с доступом к объекту и правом согласования.</p>}
    <label>Текст запроса согласования<textarea required maxLength={10000} disabled={busy} value={text} onChange={e=>setText(e.target.value)}/></label>
    <div><button type="button" disabled={busy} onClick={onClose}>Отмена</button><button disabled={busy||loading||!selected||!text.trim()}>Отправить на согласование</button></div>
    {error&&<p role="alert">{error}</p>}
  </form>;
}

export function TaskApprovalRequest({taskId,comments,approvals,reload}:{taskId:string;comments:any[];approvals:Approval[];reload:()=>Promise<void>}){
  const [open,setOpen]=useState(false),[selected,setSelected]=useState('');const trigger=useRef<HTMLButtonElement>(null);
  const eligible=comments.filter(c=>c.can_request_approval);
  const comment=eligible.find(c=>c.id===selected)||eligible[eligible.length-1];
  const close=()=>{setOpen(false);trigger.current?.focus()};
  useEffect(()=>{if(open&&selected&&!eligible.some(c=>c.id===selected)){setOpen(false);trigger.current?.focus()}},[comments,open,selected]);
  if(!comment)return null;
  return <div className="task-chat-request">
    <button ref={trigger} type="button" className="approval-request" aria-expanded={open} onClick={()=>{if(open)close();else{setSelected(comment.id);setOpen(true)}}}>Запросить согласование</button>
    {open&&<section className="task-chat-request-panel" aria-label="Запрос согласования" onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();close()}}}>
      <h3>Запрос согласования</h3>
      <label>Сообщение для согласования<select value={comment.id} onChange={e=>setSelected(e.target.value)}>{[...eligible].reverse().map(c=><option key={c.id} value={c.id}>{c.author_display}: {c.body.slice(0,100)}</option>)}</select></label>
      <blockquote>{comment.body}</blockquote>
      <ApprovalRequestForm key={comment.id} taskId={taskId} comment={comment} approvals={approvals.filter(a=>a.comment===comment.id)} reload={reload} onClose={close}/>
    </section>}
  </div>;
}
