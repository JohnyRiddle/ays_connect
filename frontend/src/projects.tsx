import React, { useEffect, useState } from "react";
import { Page, WorkApiError, workRequest } from "./workApi";
import { ProjectDetail as ProjectDetailUX } from "./ProjectDetail";
import "./projects.css";

type Navigate = (path: string) => void;
type Project = { id: string; number: string; name: string; goal: string; expected_result: string; manager: string|null; manager_name: string | null; customer:string|null; org_unit:string|null; status: string; version: number; planned_start_at: string | null; planned_end_at: string | null; is_archived: boolean };
type Employee = { id: string; display_name: string };
const root = "/projects/";
const get = <T,>(path: string) => workRequest<T>(root + path);
const post = <T,>(path: string, data: unknown, key?: string) => workRequest<T>(root + path, { method: "POST", body: JSON.stringify(data), headers:key?{"Idempotency-Key":key}:{} });
const date = (value: string | null) => value ? new Date(value).toLocaleDateString("ru-RU") : "—";
function requestKey() {
  const bytes=crypto.getRandomValues(new Uint8Array(16));
  bytes[6]=(bytes[6]&15)|64; bytes[8]=(bytes[8]&63)|128;
  const hex=Array.from(bytes,x=>x.toString(16).padStart(2,"0")).join("");
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
const statusName: Record<string, string> = { draft: "Черновик", active: "Активен", on_hold: "Приостановлен", completed: "Завершён", cancelled: "Отменён", review: "На приёмке", waiting: "Ожидание", in_progress: "В работе", open: "Открыта" };
function ErrorView({ error, retry }: { error: unknown; retry: () => void }) {
  const e = error instanceof WorkApiError ? error : null;
  return <div className="project-error" role="alert"><strong>{e?.message || "Не удалось загрузить данные."}</strong><button onClick={retry}>Повторить</button></div>;
}

function ProjectList({ navigate }: { navigate: Navigate }) {
  const [page, setPage] = useState<Page<Project> | null>(null);
  const [error, setError] = useState<unknown>();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [managerFilter, setManagerFilter] = useState("");
  const [orgFilter, setOrgFilter] = useState("");
  const [participation, setParticipation] = useState("");
  const [orgUnits, setOrgUnits] = useState<{id:string;name:string}[]>([]);
  const [pageNo, setPageNo] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [people, setPeople] = useState<Employee[]>([]);
  const [manager, setManager] = useState("");
  const [customer, setCustomer] = useState("");
  const [orgUnit, setOrgUnit] = useState("");
  const [goal, setGoal] = useState("");
  const [result, setResult] = useState("");
  const [plannedStart, setPlannedStart] = useState("");
  const [plannedEnd, setPlannedEnd] = useState("");
  const [createKey] = useState(requestKey);
  const load = () => {
    const q = new URLSearchParams({page:String(pageNo)}); if (search) q.set("search", search); if (status) q.set("status", status); if(managerFilter) q.set("manager",managerFilter); if(orgFilter) q.set("org_unit",orgFilter); if(participation) q.set("participation",participation);
    get<Page<Project>>(`?${q}`).then(setPage).catch(setError);
  };
  useEffect(load, [search, status, managerFilter, orgFilter, participation, pageNo]);
  useEffect(() => { workRequest<Page<Employee>>("/employees/").then(x => setPeople(x.results)).catch(() => {}); }, []);
  useEffect(() => { workRequest<Page<{id:string;name:string}>>("/org-units/").then(x=>setOrgUnits(x.results)).catch(()=>{}); }, []);
  const create = async () => {
    if (!name.trim() || creating) return;
    setCreating(true);
    try { const item = await post<Project>("", { name: name.trim(), manager: manager || null,
      customer:customer||null,org_unit:orgUnit||null,goal,expected_result:result,
      planned_start_at:plannedStart?new Date(plannedStart).toISOString():null,
      planned_end_at:plannedEnd?new Date(plannedEnd).toISOString():null }, createKey); navigate(`/projects/${item.id}`); }
    catch (e) { setError(e); setCreating(false); }
  };
  return <main className="project-page"><header className="project-header"><div><small>Projects</small><h1>Проекты</h1><p>Проекты, доступные по вашим правам и области доступа.</p></div><button className="project-create-trigger" type="button" aria-expanded={showCreate} onClick={() => setShowCreate(value => !value)}>{showCreate ? "Закрыть" : "Создать проект"}</button></header>
    {showCreate && <section className="project-create-panel" aria-label="Создание проекта"><h2>Новый проект</h2>
      <div className="project-create"><input autoFocus aria-label="Название нового проекта" value={name} onChange={e => setName(e.target.value)} placeholder="Название нового проекта" /><select aria-label="Руководитель проекта" value={manager} onChange={e => setManager(e.target.value)}><option value="">Руководитель не назначен</option>{people.map(x => <option key={x.id} value={x.id}>{x.display_name}</option>)}</select></div>
      <div className="project-create"><input aria-label="Цель нового проекта" value={goal} onChange={e=>setGoal(e.target.value)} placeholder="Цель" /><input aria-label="Ожидаемый результат нового проекта" value={result} onChange={e=>setResult(e.target.value)} placeholder="Ожидаемый результат" /><select aria-label="Заказчик нового проекта" value={customer} onChange={e=>setCustomer(e.target.value)}><option value="">Без заказчика</option>{people.map(x=><option key={x.id} value={x.id}>{x.display_name}</option>)}</select><select aria-label="Подразделение нового проекта" value={orgUnit} onChange={e=>setOrgUnit(e.target.value)}><option value="">Межфункциональный проект</option>{orgUnits.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><input aria-label="Плановое начало нового проекта" type="datetime-local" value={plannedStart} onChange={e=>setPlannedStart(e.target.value)} /><input aria-label="Плановое завершение нового проекта" type="datetime-local" value={plannedEnd} onChange={e=>setPlannedEnd(e.target.value)} /></div>
      <div className="project-create-actions"><button type="button" className="project-secondary-action" onClick={() => setShowCreate(false)}>Отмена</button><button type="button" onClick={create} disabled={!name.trim() || creating}>{creating ? "Создаём…" : "Создать"}</button></div>
    </section>}
    <div className="project-toolbar"><input aria-label="Поиск проектов" placeholder="Номер, название или цель" value={search} onChange={e => {setSearch(e.target.value);setPageNo(1);}} /><select aria-label="Статус проекта" value={status} onChange={e => {setStatus(e.target.value);setPageNo(1);}}><option value="">Все статусы</option>{Object.entries(statusName).slice(0,5).map(([code,label]) => <option key={code} value={code}>{label}</option>)}</select><select aria-label="Фильтр руководителя" value={managerFilter} onChange={e=>{setManagerFilter(e.target.value);setPageNo(1);}}><option value="">Все руководители</option>{people.map(x=><option key={x.id} value={x.id}>{x.display_name}</option>)}</select><select aria-label="Фильтр подразделения" value={orgFilter} onChange={e=>{setOrgFilter(e.target.value);setPageNo(1);}}><option value="">Все подразделения</option>{orgUnits.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><select aria-label="Фильтр участия" value={participation} onChange={e=>{setParticipation(e.target.value);setPageNo(1);}}><option value="">Все доступные</option><option value="mine">Участвую</option><option value="member">Участник</option><option value="managing">Руководитель</option></select></div>
    {Boolean(error) && <ErrorView error={error} retry={load} />}{!page && !error && <p>Загружаем проекты…</p>}
    <div className="project-list">{page?.results.map(item => <button key={item.id} onClick={() => navigate(`/projects/${item.id}`)}><strong>{item.number} · {item.name}</strong><span>{statusName[item.status] || item.status}{item.is_archived ? " · архив" : ""}</span><small>{item.manager_name || "Руководитель не назначен"} · до {date(item.planned_end_at)}</small></button>)}</div>
    {page && <div className="project-pager"><button disabled={!page.previous} onClick={() => setPageNo(x => x-1)}>← Назад</button><span>Страница {pageNo} · всего {page.count}</span><button disabled={!page.next} onClick={() => setPageNo(x => x+1)}>Вперёд →</button></div>}
    {page && !page.results.length && <p>Доступных проектов пока нет.</p>}
  </main>;
}

export function ProjectsRouter({ path, navigate }: { path: string; navigate: Navigate }) {
  const id = path.split("/").filter(Boolean)[1];
  return id ? <ProjectDetailUX id={id} navigate={navigate} /> : <ProjectList navigate={navigate} />;
}
