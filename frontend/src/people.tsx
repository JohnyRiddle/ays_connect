import React, { useEffect, useState } from "react";
const ROOT = (import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1").replace(/\/api\/v1\/?$/, "");
async function request(path: string, options: RequestInit = {}) {
  const token = sessionStorage.getItem("access");
  const response = await fetch(`${ROOT}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) { const values = Object.values(data).flatMap((value:any) => typeof value === "string" ? [value] : Array.isArray(value) ? value.map(String) : value && typeof value === "object" ? Object.values(value).flat().map(String) : []); throw new Error((typeof data.detail === "string" ? data.detail : values.join(" ")) || "Не удалось выполнить запрос."); }
  return data;
}

export function RegistrationPage() {
  const [form, setForm] = useState({ full_name: "", email: "" }); const [message, setMessage] = useState(""); const [error, setError] = useState("");
  async function submit(e: React.FormEvent) { e.preventDefault(); setError(""); try { const data = await request("/api/public/v1/register/", { method: "POST", body: JSON.stringify(form) }); setMessage(data.detail); } catch (e) { setError((e as Error).message); } }
  return <main className="public-people"><form className="people-card" onSubmit={submit}><a href="/" className="logo"><span>A</span> AYS Connect</a><p className="eyebrow blue">Контролируемая регистрация</p><h1>Заявка на доступ</h1>{message ? <div className="success-box">{message}<p><a href="/">Вернуться ко входу</a></p></div> : <><p className="muted">Укажите корпоративные данные. Аккаунт появится только после проверки администратором.</p><label>ФИО<input required maxLength={300} value={form.full_name} onChange={e => setForm({...form, full_name:e.target.value})}/></label><label>Рабочая электронная почта<input required type="email" value={form.email} onChange={e => setForm({...form, email:e.target.value})}/></label>{error && <div className="error">{error}</div>}<button className="primary">Отправить заявку</button></>}</form></main>;
}

export function ActivationPage({ token }: { token: string }) {
  const [context, setContext] = useState<any>(); const [password, setPassword] = useState(""); const [confirmation, setConfirmation] = useState(""); const [state, setState] = useState<"loading"|"valid"|"invalid"|"success">("loading"); const [error, setError] = useState("");
  useEffect(() => { request(`/api/public/v1/activate/${encodeURIComponent(token)}/`).then(x => {setContext(x);setState("valid")}).catch(() => setState("invalid")); }, [token]);
  async function submit(e: React.FormEvent) { e.preventDefault(); setError(""); if(password!==confirmation){setError("Пароли не совпадают.");return;} try { await request(`/api/public/v1/activate/${encodeURIComponent(token)}/`, {method:"POST", body:JSON.stringify({password,password_confirmation:confirmation})}); setState("success"); } catch(e){setError((e as Error).message);} }
  return <main className="public-people"><section className="people-card"><a href="/" className="logo"><span>A</span> AYS Connect</a>{state==="loading"&&<p>Проверяем приглашение…</p>}{state==="invalid"&&<><h1>Ссылка недоступна</h1><p className="muted">Она могла истечь, быть использована или отозвана.</p></>}{state==="success"&&<><h1>Аккаунт активирован</h1><a className="primary link-button" href="/">Войти в AYS Connect</a></>}{state==="valid"&&<form onSubmit={submit}><p className="eyebrow blue">Вас пригласили в AYS Connect</p><h1>{context.employee_name}</h1><p>{context.position}{context.organization ? ` · ${context.organization}`:""}</p><label>Пароль<input type="password" minLength={8} required value={password} onChange={e=>setPassword(e.target.value)}/></label><label>Повторите пароль<input type="password" required value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></label><small className="muted">Используйте длинный пароль, не похожий на имя или почту.</small>{error&&<div className="error">{error}</div>}<button className="primary">Активировать аккаунт</button></form>}</section></main>;
}

const labels: Record<string,string>={NO_ACCOUNT:"Нет аккаунта",INVITED:"Приглашён",PENDING_APPROVAL:"Ожидает подтверждения",ACTIVE:"Активен",BLOCKED:"Заблокирован",INVITATION_EXPIRED:"Приглашение истекло"};
const initials = (name = "") => name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "—";
export function PeopleRouter({path,navigate}:{path:string;navigate:(x:string)=>void}) {
  const [data,setData]=useState<any>(); const [error,setError]=useState(""); const [search,setSearch]=useState("");
  const id=path.match(/^\/people\/employees\/([^/]+)$/)?.[1]; const registrations=path==="/people/registrations";
  const load=()=>request(registrations?"/api/internal/v1/people/registrations/":id?`/api/internal/v1/people/employees/${id}/`:`/api/internal/v1/people/employees/?search=${encodeURIComponent(search)}`).then(setData).catch(e=>setError(e.message));
  useEffect(()=>{ load(); },[path]);
  async function employeeAction(action:string, payload:any={}){setError("");try{const result=await request(`/api/internal/v1/people/employees/${id}/${action}/`,{method:"POST",body:JSON.stringify(payload)});if(result.activation_url) await navigator.clipboard.writeText(result.activation_url);load();}catch(e){setError((e as Error).message)}}
  if(error&&!data)return <main className="work-page"><div className="error">{error}</div></main>;
  if(registrations)return <main className="work-page"><div className="page-heading"><div><p className="eyebrow blue">People</p><h1>Заявки на регистрацию</h1></div></div><div className="people-grid">{data?.results?.map((x:any)=><article className="people-card" key={x.id}><b>{x.full_name}</b><span>{x.email}</span><span className="badge">{x.status}</span>{x.status==="pending"&&<><button onClick={()=>{const employee_id=prompt("UUID сотрудника");if(employee_id)request(`/api/internal/v1/people/registrations/${x.id}/approve/`,{method:"POST",body:JSON.stringify({employee_id})}).then(load).catch(e=>setError(e.message))}}>Одобрить и пригласить</button><button onClick={()=>request(`/api/internal/v1/people/registrations/${x.id}/reject/`,{method:"POST",body:JSON.stringify({reason:"not_confirmed"})}).then(load)}>Отклонить</button></>}</article>)}</div>{error&&<div className="error">{error}</div>}</main>;
  if(id&&data)return <main className="work-page people-detail">
    <button className="people-back" onClick={()=>navigate("/people/employees")}>← К сотрудникам</button>
    <section className="people-profile-head">
      <div className="people-avatar" aria-hidden="true">{initials(data.display_name)}</div>
      <div className="people-profile-title">
        <p className="eyebrow blue">Карточка сотрудника</p>
        <h1>{data.display_name}</h1>
        <p>{data.position_name||"Должность не указана"}<span>·</span>{data.org_unit_name||"Без подразделения"}</p>
      </div>
      <span className={`badge account-${String(data.account_status).toLowerCase()}`}>{labels[data.account_status]||data.account_status}</span>
    </section>
    {error&&<div className="error">{error}</div>}
    <div className="people-columns">
      <section className="people-card people-info-card">
        <header><span>01</span><div><h2>Рабочий профиль</h2><p>Организационные данные сотрудника</p></div></header>
        <dl>
          <div><dt>Табельный номер</dt><dd>{data.employee_number||"—"}</dd></div>
          <div><dt>Должность</dt><dd>{data.position_name||"—"}</dd></div>
          <div><dt>Подразделение</dt><dd>{data.org_unit_name||"—"}</dd></div>
          <div><dt>Юридическое лицо</dt><dd>{data.legal_entity_name||"—"}</dd></div>
          <div><dt>Локация</dt><dd>{data.location_name||"—"}</dd></div>
          <div><dt>Статус сотрудника</dt><dd><span className="people-value-status">{data.status||"—"}</span></dd></div>
        </dl>
      </section>
      <section className="people-card people-account-card">
        <header><span>02</span><div><h2>Учётная запись</h2><p>Доступ к AYS Connect</p></div></header>
        <div className="people-account-summary">
          <span className="people-account-icon">@</span>
          <div><small>Рабочая электронная почта</small><strong>{data.account?.email||data.work_email||"Не указана"}</strong></div>
        </div>
        <div className="action-row">{!data.account&&<button className="primary" onClick={()=>{const email=prompt("Рабочая электронная почта");if(email)employeeAction("invite",{email})}}>Пригласить</button>}{data.account_status==="INVITED"&&<><button onClick={()=>employeeAction("invite",{email:prompt("Рабочая электронная почта")})}>Отправить повторно</button><button className="secondary-danger" onClick={()=>employeeAction("revoke-invitation")}>Отозвать</button></>}{data.account_status==="ACTIVE"&&<button className="secondary-danger" onClick={()=>employeeAction("account/block")}>Заблокировать</button>}{data.account_status==="BLOCKED"&&<button onClick={()=>employeeAction("account/unblock")}>Разблокировать</button>}</div>
      </section>
      <section className="people-card people-access-card">
        <header><span>03</span><div><h2>Доступ и группы</h2><p>Роли и функциональные связи</p></div></header>
        <div className="people-access-group"><h3>Роли</h3><div className="people-chip-list">{data.roles?.length?data.roles.map((x:any)=><span className="badge" key={x.code}>{x.name}</span>):<span className="people-empty">Роли не назначены</span>}</div></div>
        <div className="people-access-group"><h3>Функциональные группы</h3><div className="people-chip-list">{data.functional_groups?.length?data.functional_groups.map((x:any)=><span className="badge neutral" key={x.id}>{x.name}</span>):<span className="people-empty">Сотрудник не входит в группы</span>}</div></div>
      </section>
    </div>
  </main>;
  return <main className="work-page"><div className="page-heading"><div><p className="eyebrow blue">People</p><h1>Сотрудники</h1></div><button onClick={()=>navigate("/people/registrations")}>Заявки на регистрацию</button></div><form className="people-filters" onSubmit={e=>{e.preventDefault();load()}}><label>Поиск<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="ФИО, должность или подразделение"/></label><button>Найти</button></form><div className="people-table"><div className="people-row people-head"><b>Сотрудник</b><b>Должность</b><b>Подразделение</b><b>Локация</b><b>Аккаунт</b></div>{data?.results?.map((x:any)=><button className="people-row" key={x.id} onClick={()=>navigate(`/people/employees/${x.id}`)}><span className="people-person"><span className="people-list-avatar">{initials(x.display_name)}</span><span><b>{x.display_name}</b><small>{x.employee_number||"Номер не назначен"}</small></span></span><span>{x.position_name||"—"}</span><span>{x.org_unit_name||"—"}</span><span>{x.location_name||"—"}</span><span className={`badge account-${String(x.account_status).toLowerCase()}`}>{labels[x.account_status]||x.account_status}</span></button>)}</div><p className="people-total">Всего сотрудников: <b>{data?.count||0}</b></p></main>;
}
