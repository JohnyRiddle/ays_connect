import React, { useEffect, useState } from "react";
import { Page, WorkApiError, workDownload, workRequest } from "./workApi";
import "./projects.css";

type Navigate = (path: string) => void;
type Project = { id: string; number: string; name: string; goal: string; expected_result: string; manager: string|null; manager_name: string | null; customer:string|null; org_unit:string|null; status: string; version: number; planned_start_at: string | null; planned_end_at: string | null; is_archived: boolean };
type Stage = { id: string; name: string; position: number; planned_start_at: string | null; planned_end_at: string | null };
type Milestone = { id: string; name: string; due_at: string | null; required: boolean; confirmed_at: string | null; criterion: string };
type Comment = { id: string; author_name: string; body: string; created_at: string };
type Member = { id: string; employee: string; employee_name: string; role: string };
type Attachment = { id: string; original_filename: string; size: number };
type Employee = { id: string; display_name: string };
type Task = { id: string; number: string; title: string; status: string; version: number; due_at: string | null; is_overdue: boolean; project?: { stage_id: string | null } };
const root = "/projects/";
const get = <T,>(path: string) => workRequest<T>(root + path);
const post = <T,>(path: string, data: unknown, key?: string) => workRequest<T>(root + path, { method: "POST", body: JSON.stringify(data), headers:key?{"Idempotency-Key":key}:{} });
const date = (value: string | null) => value ? new Date(value).toLocaleDateString("ru-RU") : "—";
const inputDate = (value:string|null) => {if(!value)return "";const d=new Date(value);const pad=(x:number)=>String(x).padStart(2,"0");return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;};
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
    if (!name.trim()) return;
    try { const item = await post<Project>("", { name: name.trim(), manager: manager || null,
      customer:customer||null,org_unit:orgUnit||null,goal,expected_result:result,
      planned_start_at:plannedStart?new Date(plannedStart).toISOString():null,
      planned_end_at:plannedEnd?new Date(plannedEnd).toISOString():null }, createKey); navigate(`/projects/${item.id}`); }
    catch (e) { setError(e); }
  };
  return <main className="project-page"><header className="project-header"><div><small>Projects</small><h1>Проекты</h1><p>Проекты, доступные по вашим правам и области доступа.</p></div></header>
    <div className="project-toolbar"><input aria-label="Поиск проектов" placeholder="Номер, название или цель" value={search} onChange={e => {setSearch(e.target.value);setPageNo(1);}} /><select aria-label="Статус проекта" value={status} onChange={e => {setStatus(e.target.value);setPageNo(1);}}><option value="">Все статусы</option>{Object.entries(statusName).slice(0,5).map(([code,label]) => <option key={code} value={code}>{label}</option>)}</select><select aria-label="Фильтр руководителя" value={managerFilter} onChange={e=>{setManagerFilter(e.target.value);setPageNo(1);}}><option value="">Все руководители</option>{people.map(x=><option key={x.id} value={x.id}>{x.display_name}</option>)}</select><select aria-label="Фильтр подразделения" value={orgFilter} onChange={e=>{setOrgFilter(e.target.value);setPageNo(1);}}><option value="">Все подразделения</option>{orgUnits.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><select aria-label="Фильтр участия" value={participation} onChange={e=>{setParticipation(e.target.value);setPageNo(1);}}><option value="">Все доступные</option><option value="mine">Участвую</option><option value="member">Участник</option><option value="managing">Руководитель</option></select></div>
    <div className="project-create"><input aria-label="Название нового проекта" value={name} onChange={e => setName(e.target.value)} placeholder="Название нового проекта" /><select aria-label="Руководитель проекта" value={manager} onChange={e => setManager(e.target.value)}><option value="">Руководитель не назначен</option>{people.map(x => <option key={x.id} value={x.id}>{x.display_name}</option>)}</select><button onClick={create} disabled={!name.trim()}>Создать проект</button></div>
    <div className="project-create"><input aria-label="Цель нового проекта" value={goal} onChange={e=>setGoal(e.target.value)} placeholder="Цель" /><input aria-label="Ожидаемый результат нового проекта" value={result} onChange={e=>setResult(e.target.value)} placeholder="Ожидаемый результат" /><select aria-label="Заказчик нового проекта" value={customer} onChange={e=>setCustomer(e.target.value)}><option value="">Без заказчика</option>{people.map(x=><option key={x.id} value={x.id}>{x.display_name}</option>)}</select><select aria-label="Подразделение нового проекта" value={orgUnit} onChange={e=>setOrgUnit(e.target.value)}><option value="">Межфункциональный проект</option>{orgUnits.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><input aria-label="Плановое начало нового проекта" type="datetime-local" value={plannedStart} onChange={e=>setPlannedStart(e.target.value)} /><input aria-label="Плановое завершение нового проекта" type="datetime-local" value={plannedEnd} onChange={e=>setPlannedEnd(e.target.value)} /></div>
    {Boolean(error) && <ErrorView error={error} retry={load} />}{!page && !error && <p>Загружаем проекты…</p>}
    <div className="project-list">{page?.results.map(item => <button key={item.id} onClick={() => navigate(`/projects/${item.id}`)}><strong>{item.number} · {item.name}</strong><span>{statusName[item.status] || item.status}{item.is_archived ? " · архив" : ""}</span><small>{item.manager_name || "Руководитель не назначен"} · до {date(item.planned_end_at)}</small></button>)}</div>
    {page && <div className="project-pager"><button disabled={!page.previous} onClick={() => setPageNo(x => x-1)}>← Назад</button><span>Страница {pageNo} · всего {page.count}</span><button disabled={!page.next} onClick={() => setPageNo(x => x+1)}>Вперёд →</button></div>}
    {page && !page.results.length && <p>Доступных проектов пока нет.</p>}
  </main>;
}

function ProjectDetail({ id, navigate }: { id: string; navigate: Navigate }) {
  const [project, setProject] = useState<Project | null>(null);
  const [stages, setStages] = useState<Stage[]>([]);
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskPage, setTaskPage] = useState<Page<Task> | null>(null);
  const [taskPageNo, setTaskPageNo] = useState(1);
  const [comments, setComments] = useState<Comment[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [people, setPeople] = useState<Employee[]>([]);
  const [member, setMember] = useState("");
  const [linkSearch, setLinkSearch] = useState("");
  const [linkOptions, setLinkOptions] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState("");
  const [counters, setCounters] = useState<any>(null);
  const [history, setHistory] = useState<{project:{action:string;created_at:string}[];links:{action:string;task_id:string;created_at:string}[]}|null>(null);
  const [mode, setMode] = useState<"list" | "board" | "timeline">("list");
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState("");
  const [mentionIds, setMentionIds] = useState<string[]>([]);
  const [editName, setEditName] = useState("");
  const [editGoal, setEditGoal] = useState("");
  const [editResult, setEditResult] = useState("");
  const [editManager, setEditManager] = useState("");
  const [editCustomer, setEditCustomer] = useState("");
  const [editOrgUnit, setEditOrgUnit] = useState("");
  const [editStart, setEditStart] = useState("");
  const [editEnd, setEditEnd] = useState("");
  const [orgUnits, setOrgUnits] = useState<{id:string;name:string}[]>([]);
  const [stageName, setStageName] = useState("");
  const [milestoneName, setMilestoneName] = useState("");
  const [milestoneDue, setMilestoneDue] = useState("");
  const [milestoneStage, setMilestoneStage] = useState("");
  const [milestoneCriterion, setMilestoneCriterion] = useState("");
  const [milestoneRequired, setMilestoneRequired] = useState(false);
  const [milestoneResponsible, setMilestoneResponsible] = useState("");
  const [memberRole, setMemberRole] = useState("member");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskCreateKey, setTaskCreateKey] = useState(requestKey);
  const [taskStage, setTaskStage] = useState("");
  const [taskDue, setTaskDue] = useState("");
  const [taskPriority, setTaskPriority] = useState("normal");
  const [taskAcceptance, setTaskAcceptance] = useState("none");
  const [template, setTemplate] = useState("");
  const [templates, setTemplates] = useState<{id:string;name:string}[]>([]);
  const [targets, setTargets] = useState<{ id: string; display_name: string }[]>([]);
  const [responsibleTarget, setResponsibleTarget] = useState("");
  const [executorTarget, setExecutorTarget] = useState("");
  const load = async () => {
    try {
      const [p, s, m, t, c, summary, membersList, files, events] = await Promise.all([
        get<Project>(`${id}/`), get<Stage[]>(`${id}/stages/`), get<Milestone[]>(`${id}/milestones/`),
        get<Page<Task>>(`${id}/tasks/?page=${taskPageNo}`), get<Comment[]>(`${id}/comments/`), get<any>(`${id}/counters/`),
        get<Member[]>(`${id}/members/`), get<Attachment[]>(`${id}/attachments/`),
        get<{project:{action:string;created_at:string}[];links:{action:string;task_id:string;created_at:string}[]}>(`${id}/history/`),
      ]);
      setProject(p); setEditName(p.name); setEditGoal(p.goal); setEditResult(p.expected_result || "");setEditManager(p.manager||"");setEditCustomer(p.customer||"");setEditOrgUnit(p.org_unit||"");setEditStart(inputDate(p.planned_start_at));setEditEnd(inputDate(p.planned_end_at)); setStages(s); setMilestones(m); setTasks(t.results); setTaskPage(t); setComments(c); setCounters(summary); setMembers(membersList); setAttachments(files); setHistory(events); setError(undefined);
    } catch (e) { setError(e); }
  };
  useEffect(() => { load(); }, [id, taskPageNo]);
  useEffect(() => { workRequest<Page<Employee>>("/employees/").then(x => setPeople(x.results)).catch(() => {}); }, []);
  useEffect(() => { workRequest<Page<{id:string;name:string}>>("/org-units/").then(x=>setOrgUnits(x.results)).catch(()=>{}); }, []);
  useEffect(() => { workRequest<Page<{ id: string; display_name: string }>>("/assignment-targets/").then(x => setTargets(x.results)).catch(() => {}); }, []);
  useEffect(() => { workRequest<Page<{id:string;name:string}>>("/task-templates/").then(x=>setTemplates(x.results)).catch(()=>{}); }, []);
  useEffect(() => { if (!linkSearch.trim()) { setLinkOptions([]); return; } const timer = setTimeout(() => workRequest<Page<Task>>(`/tasks/?search=${encodeURIComponent(linkSearch)}`).then(x => setLinkOptions(x.results)).catch(() => setLinkOptions([])), 250); return () => clearTimeout(timer); }, [linkSearch]);
  const action = async (path: string, data: unknown, key?: string, method: "POST"|"PATCH" = "POST") => {
    setBusy(true); try { if(method==="PATCH") await workRequest(`${root}${id}/${path}/`,{method,body:JSON.stringify(data)});else await post(`${id}/${path}/`, data, key); await load(); if (path==="create-task") setTaskCreateKey(requestKey()); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const update = async () => { setBusy(true); try { await workRequest(`${root}${id}/`, { method:"PATCH", body:JSON.stringify({version:project?.version,name:editName.trim(),goal:editGoal,expected_result:editResult,
    manager:editManager||null,customer:editCustomer||null,org_unit:editOrgUnit||null,
    planned_start_at:editStart?new Date(editStart).toISOString():null,
    planned_end_at:editEnd?new Date(editEnd).toISOString():null}) }); await load(); } catch(e) {setError(e);} finally {setBusy(false);} };
  if (error && !project) return <main className="project-page"><ErrorView error={error} retry={load} /></main>;
  if (!project) return <main className="project-page">Загружаем проект…</main>;
  const editable = !busy && !project.is_archived && !["completed", "cancelled"].includes(project.status);
  const stageLabel = (task: Task) => stages.find(s => s.id === task.project?.stage_id)?.name || "Без этапа";
  const taskCommand = async (task:Task, command:"move-stage"|"unlink-task", stageId?:string) => {
    try {
      const current=await workRequest<any>(`/tasks/${task.id}/`);
      const reason=command==="unlink-task"?window.prompt("Причина отвязки задачи"):"";
      if(command==="unlink-task" && !reason?.trim()) return;
      await action(command,{project_version:project.version,task_version:current.version,task:task.id,
        ...(command==="move-stage"?{stage:stageId||null}:{reason})});
    } catch(e) { setError(e); }
  };
  const boardMove = async (task:Task, target:string) => {
    const commands:Record<string,string>={
      "draft:open":"publish","open:in_progress":"start","in_progress:waiting":"pause",
      "waiting:in_progress":"resume","in_progress:review":"complete","in_progress:completed":"complete",
      "review:completed":"accept","review:in_progress":"reject","completed:in_progress":"reopen",
      "draft:cancelled":"cancel","open:cancelled":"cancel","in_progress:cancelled":"cancel",
      "waiting:cancelled":"cancel","review:cancelled":"cancel"
    };
    const command=commands[`${task.status}:${target}`];
    if(!command){setError(new Error("Для этого перехода откройте задачу Work и выберите разрешённую операцию."));return;}
    const payload:Record<string,unknown>={version:task.version};
    if(command==="pause"){
      const reason=window.prompt("Причина ожидания: waiting_requester, waiting_external, waiting_material, waiting_approval или waiting_other","waiting_approval");
      if(!reason)return;payload.reason=reason;
      if(reason==="waiting_other"){const comment=window.prompt("Комментарий к ожиданию");if(!comment?.trim())return;payload.comment=comment;}
    }
    if(["reject","reopen","cancel"].includes(command)){
      const reason=window.prompt("Причина перехода задачи Work");if(!reason?.trim())return;payload.reason=reason;
    }
    try{await workRequest(`/tasks/${task.id}/${command}/`,{method:"POST",body:JSON.stringify(payload)});await load();}
    catch(e){setError(e);}
  };
  const taskCard = (task: Task) => <div key={task.id} className={task.is_overdue ? "project-task overdue" : "project-task"} draggable={mode==="board"} onDragStart={e=>e.dataTransfer.setData("text/plain",task.id)} onClick={() => navigate(`/tasks/${task.id}`)} role="button" tabIndex={0} onKeyDown={e => {if(e.key==="Enter")navigate(`/tasks/${task.id}`);}}><strong>{task.number} · {task.title}</strong><span>{statusName[task.status] || task.status} · {stageLabel(task)}</span><small>Срок: {date(task.due_at)}</small>{editable && <div className="project-task-controls" onClick={e=>e.stopPropagation()}><select aria-label={`Этап задачи ${task.number}`} value={task.project?.stage_id||""} onChange={e=>taskCommand(task,"move-stage",e.target.value)}><option value="">Без этапа</option>{stages.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><button onClick={()=>taskCommand(task,"unlink-task")}>Отвязать</button></div>}</div>;
  return <main className="project-page"><button className="project-back" onClick={() => navigate("/projects")}>← Все проекты</button><header className="project-header"><div><small>{project.number} · {statusName[project.status] || project.status}{project.is_archived ? " · архив" : ""}</small><h1>{project.name}</h1><p>{project.goal || "Цель проекта не указана"}</p><span>Руководитель: {project.manager_name || "не назначен"} · срок: {date(project.planned_start_at)} — {date(project.planned_end_at)}</span></div><div className="project-actions">{project.status === "draft" && <button disabled={!editable} onClick={() => action("start", { version: project.version })}>Начать</button>}{project.status === "active" && <button disabled={!editable} onClick={() => action("hold", { version: project.version })}>Приостановить</button>}{project.status === "on_hold" && <button disabled={!editable} onClick={() => action("start", { version: project.version })}>Продолжить</button>}{["active", "on_hold"].includes(project.status) && <button disabled={!editable} onClick={() => action("complete", { version: project.version })}>Завершить</button>}{["draft","active","on_hold"].includes(project.status) && <button disabled={!editable} onClick={() => { const reason=window.prompt("Причина отмены проекта"); if(reason?.trim()) action("cancel",{version:project.version,reason}); }}>Отменить</button>}{project.status === "completed" && <button disabled={busy || project.is_archived} onClick={() => { const reason = window.prompt("Причина повторного открытия"); if (reason?.trim()) action("reopen", { version: project.version, reason }); }}>Открыть повторно</button>}{project.status === "cancelled" && !project.is_archived && <button disabled={busy} onClick={() => {const reason=window.prompt("Причина восстановления проекта");if(reason?.trim()) action("restore",{version:project.version,reason});}}>Восстановить</button>}{["completed","cancelled"].includes(project.status) && <button disabled={busy} onClick={() => {const reason=window.prompt(project.is_archived?"Причина возврата из архива":"Причина архивирования");if(reason?.trim()) action(project.is_archived?"unarchive":"archive",{version:project.version,reason});}}>{project.is_archived?"Вернуть из архива":"Архивировать"}</button>}</div></header>
    {Boolean(error) && <ErrorView error={error} retry={load} />}
    {editable && <section className="project-section"><h2>Параметры проекта</h2><div className="project-create"><input aria-label="Название проекта" value={editName} onChange={e=>setEditName(e.target.value)} /><input aria-label="Цель проекта" value={editGoal} onChange={e=>setEditGoal(e.target.value)} /><input aria-label="Ожидаемый результат" value={editResult} onChange={e=>setEditResult(e.target.value)} /><select aria-label="Руководитель проекта в карточке" value={editManager} onChange={e=>setEditManager(e.target.value)}><option value="">Не назначен</option>{people.map(x=><option key={x.id} value={x.id}>{x.display_name}</option>)}</select><select aria-label="Заказчик проекта" value={editCustomer} onChange={e=>setEditCustomer(e.target.value)}><option value="">Без заказчика</option>{people.map(x=><option key={x.id} value={x.id}>{x.display_name}</option>)}</select><select aria-label="Подразделение проекта" value={editOrgUnit} onChange={e=>setEditOrgUnit(e.target.value)}><option value="">Межфункциональный</option>{orgUnits.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><input aria-label="Плановое начало проекта" type="datetime-local" value={editStart} onChange={e=>setEditStart(e.target.value)} /><input aria-label="Плановое завершение проекта" type="datetime-local" value={editEnd} onChange={e=>setEditEnd(e.target.value)} /><button disabled={!editName.trim() || busy} onClick={update}>Сохранить</button></div></section>}
    <div className="project-metrics"><div><b>{counters?.progress_percent == null ? "—" : `${counters.progress_percent}%`}</b><span>Прогресс по доступным задачам</span></div><div><b>{counters?.active ?? "—"}</b><span>В работе</span></div><div><b>{counters?.overdue ?? "—"}</b><span>Просрочено</span></div><div><b>{counters?.review ?? "—"}</b><span>На приёмке</span></div><div><b>{counters?.cancelled ?? "—"}</b><span>Отменено</span></div></div>
    <section className="project-section"><h2>Ближайшие контрольные точки</h2>{counters?.next_milestones?.map((m:Milestone) => <div className="project-row" key={m.id}><strong>{m.name}</strong><small>{date(m.due_at)}</small></div>)}{!counters?.next_milestones?.length && <p>Предстоящих точек нет.</p>}</section>
    <section className="project-section"><h2>Задачи по ответственным</h2><p>Количество доступных задач, без оценки часов работы.</p>{counters?.by_responsible?.map((x:{employee_id:string|null;employee_name:string;active:number;overdue:number})=><div className="project-row" key={x.employee_id||"none"}><strong>{x.employee_name}</strong><small>Активных: {x.active} · просроченных: {x.overdue}</small></div>)}{!counters?.by_responsible?.length && <p>Доступных задач нет.</p>}</section>
    <section className="project-section"><div className="project-section-title"><h2>Задачи</h2><div className="project-tabs">{(["list", "board", "timeline"] as const).map(x => <button key={x} className={mode === x ? "selected" : ""} onClick={() => setMode(x)}>{x === "list" ? "Список" : x === "board" ? "Доска" : "Временная шкала"}</button>)}</div></div><div className="project-create"><input aria-label="Название проектной задачи" value={taskTitle} onChange={e => setTaskTitle(e.target.value)} placeholder="Название задачи Work" /><select aria-label="Этап новой задачи" value={taskStage} onChange={e => setTaskStage(e.target.value)}><option value="">Без этапа</option>{stages.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select><input aria-label="Срок новой задачи" type="datetime-local" value={taskDue} onChange={e => setTaskDue(e.target.value)} /><select aria-label="Приоритет новой задачи" value={taskPriority} onChange={e => setTaskPriority(e.target.value)}>{["low", "normal", "high", "critical"].map(x => <option key={x} value={x}>{x}</option>)}</select><select aria-label="Приёмка новой задачи" value={taskAcceptance} onChange={e => setTaskAcceptance(e.target.value)}><option value="none">Без приёмки</option><option value="author">Автор</option><option value="responsible">Ответственный</option></select><select aria-label="Ответственный новой задачи" value={responsibleTarget} onChange={e => setResponsibleTarget(e.target.value)}><option value="">Не назначен</option>{targets.map(x => <option key={x.id} value={x.id}>{x.display_name}</option>)}</select><select aria-label="Исполнитель новой задачи" value={executorTarget} onChange={e => setExecutorTarget(e.target.value)}><option value="">Не назначен</option>{targets.map(x => <option key={x.id} value={x.id}>{x.display_name}</option>)}</select><button disabled={!editable || !taskTitle.trim()} onClick={async () => { await action("create-task", { project_version: project.version, title: taskTitle.trim(), stage: taskStage || null, due_at: taskDue ? new Date(taskDue).toISOString() : null, priority: taskPriority, acceptance_policy: taskAcceptance, responsible_target: responsibleTarget || null, executor_target: executorTarget || null }, taskCreateKey); setTaskTitle(""); }}>Создать задачу</button></div>
      <div className="project-create"><input aria-label="Поиск задачи для привязки" value={linkSearch} onChange={e => setLinkSearch(e.target.value)} placeholder="Найти задачу Work" /><select aria-label="Выбранная задача" value={selectedTask} onChange={e => setSelectedTask(e.target.value)}><option value="">Выберите задачу</option>{linkOptions.filter(t => !t.project).map(t => <option key={t.id} value={t.id}>{t.number} · {t.title}</option>)}</select><button disabled={!editable || !selectedTask} onClick={async () => { const task = linkOptions.find(t => t.id === selectedTask); if (!task) return; const detail = await workRequest<any>(`/tasks/${task.id}/`); await action("link-task", { project_version: project.version, task_version: detail.version, task: task.id }); setLinkSearch(""); setSelectedTask(""); }}>Привязать</button></div>
      <div className="project-create"><select aria-label="Шаблон новой задачи" value={template} onChange={e=>setTemplate(e.target.value)}><option value="">Выберите шаблон Work</option>{templates.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><select aria-label="Этап задачи из шаблона" value={taskStage} onChange={e=>setTaskStage(e.target.value)}><option value="">Без этапа</option>{stages.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><button disabled={!editable || !template} onClick={async()=>{await action("create-task",{project_version:project.version,template,stage:taskStage||null},taskCreateKey);setTemplate("");}}>Создать из шаблона</button></div>
      {mode === "list" && <div className="project-task-list">{tasks.map(taskCard)}</div>}
      {mode === "board" && <div className="project-board">{["draft", "open", "in_progress", "waiting", "review", "completed", "cancelled"].map(status => <div key={status} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();const task=tasks.find(t=>t.id===e.dataTransfer.getData("text/plain"));if(task)boardMove(task,status);}}><h3>{statusName[status] || status}</h3>{tasks.filter(t => t.status === status).map(taskCard)}</div>)}</div>}
      {mode === "timeline" && <div className="project-timeline">{[...tasks.map(t=>({kind:"task" as const,due:t.due_at,item:t})),...milestones.map(m=>({kind:"milestone" as const,due:m.due_at,item:m}))].sort((a,b)=>(a.due||"9999").localeCompare(b.due||"9999")).map(x=>x.kind==="task"?taskCard(x.item):<div className="project-row" key={x.item.id}><strong>Контрольная точка · {x.item.name}</strong><small>Срок: {date(x.item.due_at)}</small></div>)}</div>}
      {!tasks.length && <p>Доступных задач пока нет.</p>}
      {taskPage && <div className="project-pager"><button disabled={!taskPage.previous} onClick={() => setTaskPageNo(x => x-1)}>← Назад</button><span>Страница {taskPageNo} · всего доступно {taskPage.count}</span><button disabled={!taskPage.next} onClick={() => setTaskPageNo(x => x+1)}>Вперёд →</button></div>}
    </section>
    <div className="project-columns"><section className="project-section"><h2>Этапы</h2>{stages.map(s => <div className="project-row" key={s.id}><strong>{s.position}. {s.name}</strong><small>{date(s.planned_start_at)} — {date(s.planned_end_at)}</small>{editable && <><button onClick={()=>{const name=window.prompt("Название этапа",s.name);if(name?.trim())action(`stages/${s.id}`,{version:project.version,name:name.trim()},undefined,"PATCH");}}>Изменить</button><button onClick={()=>action(`stages/${s.id}/delete`,{version:project.version})}>Удалить пустой этап</button></>}</div>)}<div className="project-create"><input aria-label="Название этапа" value={stageName} onChange={e => setStageName(e.target.value)} placeholder="Новый этап" /><button disabled={!editable || !stageName.trim()} onClick={async () => { await action("stages", { version: project.version, name: stageName.trim(), position: stages.length + 1 }); setStageName(""); }}>Добавить</button></div></section>
      <section className="project-section"><h2>Контрольные точки</h2>{milestones.map(m => <div className="project-row" key={m.id}><strong>{m.name}{m.required ? " · обязательная" : ""}</strong><small>{m.confirmed_at ? `Подтверждена ${date(m.confirmed_at)}` : `Срок ${date(m.due_at)}`}</small><p>{m.criterion}</p>{!m.confirmed_at && editable && <button onClick={() => {const name=window.prompt("Название контрольной точки",m.name);if(name?.trim())action(`milestones/${m.id}`,{version:project.version,name:name.trim()},undefined,"PATCH");}}>Изменить</button>}{!m.confirmed_at && editable && <button onClick={() => {const comment=window.prompt("Комментарий к подтверждению");if(comment!==null) action(`milestones/${m.id}/confirm`, { project_version: project.version, comment });}}>Подтвердить</button>}{m.confirmed_at && editable && <button onClick={()=>{const comment=window.prompt("Причина повторного открытия контрольной точки");if(comment?.trim()) action(`milestones/${m.id}/reopen`,{project_version:project.version,comment});}}>Открыть повторно</button>}</div>)}<div className="project-create"><input aria-label="Название контрольной точки" value={milestoneName} onChange={e => setMilestoneName(e.target.value)} placeholder="Новая контрольная точка" /><input aria-label="Критерий контрольной точки" value={milestoneCriterion} onChange={e=>setMilestoneCriterion(e.target.value)} placeholder="Критерий достижения" /><input aria-label="Срок контрольной точки" type="datetime-local" value={milestoneDue} onChange={e=>setMilestoneDue(e.target.value)} /><select aria-label="Этап контрольной точки" value={milestoneStage} onChange={e=>setMilestoneStage(e.target.value)}><option value="">Без этапа</option>{stages.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><select aria-label="Ответственный за контрольную точку" value={milestoneResponsible} onChange={e=>setMilestoneResponsible(e.target.value)}><option value="">Не назначен</option>{people.map(x=><option key={x.id} value={x.id}>{x.display_name}</option>)}</select><label className="project-check"><input type="checkbox" checked={milestoneRequired} onChange={e=>setMilestoneRequired(e.target.checked)} />Обязательная</label><button disabled={!editable || !milestoneName.trim()} onClick={async () => { await action("milestones", { version: project.version, name: milestoneName.trim(),criterion:milestoneCriterion,required:milestoneRequired,due_at:milestoneDue?new Date(milestoneDue).toISOString():null,stage:milestoneStage||null,responsible:milestoneResponsible||null }); setMilestoneName("");setMilestoneCriterion("");setMilestoneDue(""); }}>Добавить</button></div></section></div>
    <div className="project-columns"><section className="project-section"><h2>Участники</h2>{members.map(x => <div className="project-row" key={x.id}><strong>{x.employee_name}</strong><small>{x.role}</small>{editable && x.role!=="manager" && <button onClick={()=>action(`members/${x.id}/remove`,{version:project.version})}>Убрать участника</button>}</div>)}<div className="project-create"><select aria-label="Новый участник" value={member} onChange={e => setMember(e.target.value)}><option value="">Выберите сотрудника</option>{people.filter(x => !members.some(m => m.employee === x.id)).map(x => <option key={x.id} value={x.id}>{x.display_name}</option>)}</select><select aria-label="Роль нового участника" value={memberRole} onChange={e=>setMemberRole(e.target.value)}><option value="member">Участник</option><option value="observer">Наблюдатель</option></select><button disabled={!editable || !member} onClick={async () => { await action("members", { version: project.version, employee: member, role: memberRole }); setMember(""); }}>Добавить</button></div></section>
      <section className="project-section"><h2>Документы</h2>{attachments.map(x => <div className="project-row" key={x.id}><strong>{x.original_filename}</strong><small>{x.size} байт</small><button onClick={() => workDownload(`${root}${id}/attachments/${x.id}/download/`, x.original_filename).catch(setError)}>Скачать</button></div>)}<input aria-label="Загрузить документ проекта" type="file" disabled={!editable} onChange={async e => { const file = e.target.files?.[0]; if (!file) return; const data = new FormData(); data.append("file", file); setBusy(true); try { await workRequest(`${root}${id}/attachments/`, { method: "POST", body: data }); await load(); } catch (err) { setError(err); } finally { setBusy(false); e.target.value = ""; } }} /></section></div>
    <section className="project-section"><h2>Обсуждение</h2>{comments.map(c => <div className="project-row" key={c.id}><strong>{c.author_name}</strong><p>{c.body}</p><small>{date(c.created_at)}</small></div>)}<div className="project-create"><input aria-label="Комментарий проекта" value={comment} onChange={e => setComment(e.target.value)} placeholder="Написать комментарий" /><select aria-label="Упомянуть сотрудника" value={mentionIds[0]||""} onChange={e=>setMentionIds(e.target.value?[e.target.value]:[])}><option value="">Без упоминания</option>{people.map(x=><option key={x.id} value={x.id}>{x.display_name}</option>)}</select><button disabled={busy || !comment.trim()} onClick={async () => { await action("comments", { body: comment.trim(), mentions: mentionIds }); setComment("");setMentionIds([]); }}>Отправить</button></div></section>
    <section className="project-section"><h2>История</h2>{history?.project.map((x,i) => <div className="project-row" key={`p-${i}`}><strong>{x.action}</strong><small>{date(x.created_at)}</small></div>)}{history?.links.map((x,i) => <div className="project-row" key={`l-${i}`}><strong>{x.action} · задача {x.task_id}</strong><small>{date(x.created_at)}</small></div>)}</section>
  </main>;
}

export function ProjectsRouter({ path, navigate }: { path: string; navigate: Navigate }) {
  const id = path.split("/").filter(Boolean)[1];
  return id ? <ProjectDetail id={id} navigate={navigate} /> : <ProjectList navigate={navigate} />;
}
