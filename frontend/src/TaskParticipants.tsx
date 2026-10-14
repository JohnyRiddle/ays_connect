import React, { useEffect, useId, useRef, useState } from 'react';
import { workRequest } from './workApi';

export function DepartmentFields({ value, onChange, location = '', executor = '', onExecutor, fixed = false, assignmentType = 'executor' }: { value: string; onChange: (value: string) => void; location?: string; executor?: string; onExecutor?: (value: string) => void; fixed?: boolean; assignmentType?: string }) {
  const [departments, setDepartments] = useState<any[]>([]);
  const [options, setOptions] = useState<any>();
  const [error, setError] = useState('');
  useEffect(() => {
    workRequest<any>('/tasks/assignment-options/').then(x => setDepartments(x.departments)).catch(e => setError(e.message));
  }, []);
  useEffect(() => {
    let current = true;
    setOptions(undefined); setError('');
    if (value) workRequest<any>(`/tasks/assignment-options/?department=${encodeURIComponent(value)}&location=${encodeURIComponent(location)}`).then(x => { if (current) setOptions(x); }).catch(e => { if (current) setError(e.message); });
    return () => { current = false; };
  }, [value, location]);
  return <>
    <label className="work-field"><span>Ответственное подразделение *</span><select required disabled={fixed} value={value} onChange={e => { onChange(e.target.value); onExecutor?.(''); }}><option value="">Выберите подразделение</option>{departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
    <p role={error ? 'alert' : undefined}>{error || (options ? `Ответственный: ${options.responsible.name}` : value ? 'Проверяем руководителя…' : 'Ответственный определится по подразделению.')}</p>
    {onExecutor && <label className="work-field"><span>{assignmentType === 'responsible' ? 'Ответственный руководитель' : 'Исполнитель'}</span><select value={executor} disabled={!options} onChange={e => onExecutor(e.target.value)}><option value="">{fixed ? 'Выберите сотрудника' : 'Назначить позднее'}</option>{(assignmentType === 'responsible' ? options ? [options.responsible] : [] : options?.executors)?.map((e: any) => <option key={e.target_id} value={e.target_id}>{e.name}</option>)}</select></label>}
  </>;
}

export function ParticipantPicker({ taskId, selected, onChange, mode = 'mention' }: { taskId: string; selected: string[]; onChange: (value: string[]) => void; mode?: 'mention' | 'watcher' }) {
  const [search, setSearch] = useState('');
  const [choices, setChoices] = useState<any[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    let current = true;
    const timer = window.setTimeout(() => workRequest<any>(`/tasks/${taskId}/participant-options/?search=${encodeURIComponent(search)}`).then(x => { if (current) { setChoices(x.results); setError(''); } }).catch(e => { if (current) setError(e.message); }), 200);
    return () => { current = false; window.clearTimeout(timer); };
  }, [taskId, search]);
  return <div className="work-participant-picker">
    <label className="work-field"><span>{mode === 'mention' ? '@Упоминания' : 'Добавить наблюдателей'}</span><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Поиск сотрудника" /></label>
    {error && <p role="alert">{error}</p>}
    <div className="work-participant-results">{choices.map(e => <label key={e.id}><input type="checkbox" checked={selected.includes(e.id)} onChange={() => onChange(selected.includes(e.id) ? selected.filter(id => id !== e.id) : [...selected, e.id])} /> {e.name}{!e.has_access && <small> · нет доступа: упоминание его не откроет; руководитель может добавить наблюдателем</small>}</label>)}</div>
    {selected.length > 0 && <small>Выбрано: {selected.length} <button type="button" onClick={() => onChange([])}>Очистить</button></small>}
  </div>;
}

export function WatcherSearch({taskId,excluded,busy,onAdd}: {taskId:string;excluded:string[];busy:boolean;onAdd:(id:string)=>Promise<void>}) {
  const [search,setSearch]=useState('');
  const [choices,setChoices]=useState<any[]>([]);
  const [open,setOpen]=useState(false);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [active,setActive]=useState(-1);
  const listId=useId();
  const input=useRef<HTMLInputElement>(null);
  useEffect(()=>{
    let current=true;
    setChoices([]);setActive(-1);setError('');
    if(!search.trim()){setLoading(false);return;}
    setLoading(true);
    const timer=window.setTimeout(()=>workRequest<any>(`/tasks/${taskId}/participant-options/?search=${encodeURIComponent(search.trim())}`)
      .then(x=>{if(current)setChoices(x.results);})
      .catch(e=>{if(current)setError(e.message);})
      .finally(()=>{if(current)setLoading(false);}),200);
    return ()=>{current=false;window.clearTimeout(timer);};
  },[taskId,search]);
  const results=choices.filter(e=>!excluded.includes(e.id));
  const visible=open&&!!search.trim();
  const add=async(id:string)=>{setOpen(false);try{await onAdd(id);setSearch('');input.current?.focus();}catch(e){setError(e instanceof Error?e.message:'Не удалось добавить наблюдателя');setOpen(true);}};
  return <div className="watcher-search" onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget as Node))setOpen(false);}}>
    <input ref={input} role="combobox" aria-label="Добавить наблюдателя" placeholder="Введите фамилию…" autoComplete="off" value={search} disabled={busy} aria-expanded={visible} aria-controls={listId} aria-autocomplete="list" aria-activedescendant={visible&&active>=0&&results[active]?`${listId}-${active}`:undefined}
      onFocus={()=>setOpen(true)} onChange={e=>{setSearch(e.target.value);setOpen(true);}} onKeyDown={e=>{
        if(e.key==='Escape'){setOpen(false);setActive(-1);}
        if(e.key==='ArrowDown'){e.preventDefault();setOpen(true);setActive(i=>Math.min(i+1,results.length-1));}
        if(e.key==='ArrowUp'){e.preventDefault();setActive(i=>Math.max(i-1,0));}
        if(e.key==='Enter'&&visible&&results[active]){e.preventDefault();void add(results[active].id);}
      }}/>
    {visible&&<div className="watcher-dropdown"><div id={listId} role="listbox" aria-label="Найденные сотрудники">{results.map((person,index)=><button key={person.id} id={`${listId}-${index}`} type="button" role="option" aria-selected={active===index} onMouseDown={e=>e.preventDefault()} onClick={()=>void add(person.id)}>{person.name}</button>)}</div>
      {loading&&<p role="status">Поиск…</p>}{error&&<p role="alert">{error}</p>}{!loading&&!error&&!results.length&&<p role="status">Сотрудники не найдены</p>}</div>}
  </div>;
}

export function TaskSettings({ task, reload, onError }: { task: any; reload: () => void; onError: (e: any) => void }) {
  const [department, setDepartment] = useState(task.responsible_department || '');
  const [priority, setPriority] = useState(task.priority);
  const [busy, setBusy] = useState(false);
  return <details><summary>Изменить параметры</summary><form onSubmit={async e => {
    e.preventDefault(); setBusy(true);
    const data: any = {version: task.version};
    if (department !== task.responsible_department) data.responsible_department = department;
    if (task.active_priority !== null && priority !== task.priority) data.priority = priority;
    try { await workRequest(`/tasks/${task.id}/`, {method: 'PATCH', body: JSON.stringify(data)}); reload(); } catch(e) { onError(e); } finally { setBusy(false); }
  }}><DepartmentFields fixed={!task.can_change_department} value={department} onChange={setDepartment} location={task.location || ''} />
  {task.active_priority !== null && <label className="work-field"><span>Приоритет</span><select disabled={!task.available_actions?.includes('change_deadline')} value={priority} onChange={e => setPriority(e.target.value)}>{[['blocking','Блокирующая'],['critical','Критическая'],['high','Высокая'],['normal','Обычная'],['low','Низкая']].map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select><small>Срок пересчитается от создания. Для блокирующей задачи сначала задайте явный дедлайн с причиной.</small></label>}
  <button disabled={busy || !department}>Сохранить</button></form></details>;
}
