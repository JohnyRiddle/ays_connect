import {useEffect, useState} from 'react';
import {lookupApi} from './workApi';

export function TaskLocationField({value, onChange, disabled=false}: {value:string; onChange:(value:string)=>void; disabled?:boolean}) {
  const [locations,setLocations]=useState<any[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [attempt,setAttempt]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();setLoading(true);setError('');
    lookupApi.locations(controller.signal).then(data=>{if(!controller.signal.aborted)setLocations(data.results);})
      .catch(e=>{if(!controller.signal.aborted)setError(e.message);})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[attempt]);
  const choices=locations.filter(x=>!x.is_archived && x.is_active!==false);
  return <div><label className="work-field"><span>Объект / локация</span>
    <select aria-label="Объект / локация" disabled={disabled||loading||!!error} value={value} onChange={e=>onChange(e.target.value)}>
      <option value="">Не указано</option>
      {value&&!choices.some(x=>x.id===value)&&<option value={value} disabled>Текущий объект (сохранён)</option>}
      {choices.map(x=><option key={x.id} value={x.id}>{x.name}{x.code?` · ${x.code}`:''}</option>)}
    </select></label>
    {loading&&<p role="status">Загружаем объекты…</p>}
    {error&&<p role="alert">{error} <button type="button" disabled={disabled} onClick={()=>setAttempt(x=>x+1)}>Повторить загрузку объектов</button></p>}
  </div>;
}
