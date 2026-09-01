import React, { useEffect, useState } from "react";
import {
  AssignmentTarget,
  lookupApi,
  Page,
  requestsApi,
  tasksApi,
  WorkApiError,
} from "./workApi";
type Navigate = (path: string) => void;
const labels: Record<string, string> = {
  draft: "Черновик",
  open: "Открыта",
  in_progress: "В работе",
  waiting: "Ожидание",
  review: "На проверке",
  completed: "Завершена",
  cancelled: "Отменена",
  new: "Новая",
  assigned: "Назначена",
  waiting_requester: "Ожидает заявителя",
  waiting_external: "Внешнее ожидание",
  resolved: "Решена",
  closed: "Закрыта",
  low: "Низкий",
  normal: "Обычный",
  high: "Высокий",
  critical: "Критический",
};
const actionLabels: Record<string, string> = {
  publish: "Опубликовать",
  start: "Начать",
  pause: "Приостановить",
  resume: "Продолжить",
  complete: "Завершить",
  accept: "Принять",
  reject: "Отклонить",
  reopen: "Переоткрыть",
  cancel: "Отменить",
  reassign: "Переназначить",
  deadline: "Изменить срок",
  change_deadline: "Изменить срок",
  assign: "Назначить",
  wait_requester: "Ожидать заявителя",
  wait_external: "Внешнее ожидание",
  resolve: "Решить",
  close: "Закрыть",
  watch: "Наблюдать",
  unwatch: "Не наблюдать",
};
const fmt = (value?: string | null) =>
  value
    ? new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "—";
const person = (value: any) =>
  value?.display_name || value?.full_name || value?.name || value || "—";

function ErrorState({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: () => void;
}) {
  const e = error instanceof WorkApiError ? error : null;
  let message = e?.message || "Не удалось загрузить данные.";
  if (e?.kind === "forbidden") message = "Недостаточно прав для просмотра.";
  if (e?.kind === "not_found") message = "Объект недоступен или не найден.";
  return (
    <div className="work-error" role="alert">
      <b>{message}</b>
      {e?.requestId && <small>Код обращения: {e.requestId}</small>}
      {onRetry && <button onClick={onRetry}>Повторить</button>}
    </div>
  );
}
function Pager({
  page,
  onPage,
}: {
  page: Page<any>;
  onPage: (n: number) => void;
}) {
  return (
    <div className="work-pager">
      <button disabled={!page.previous} onClick={() => onPage(-1)}>
        Назад
      </button>
      <span>{page.count} записей</span>
      <button disabled={!page.next} onClick={() => onPage(1)}>
        Далее
      </button>
    </div>
  );
}

function AssignmentSelector({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (id: string) => void;
  label: string;
}) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<AssignmentTarget[]>([]);
  const [error, setError] = useState(false);
  useEffect(() => {
    const timer = setTimeout(
      () =>
        lookupApi
          .targets(query)
          .then((x) => {
            setItems(x.results);
            setError(false);
          })
          .catch(() => setError(true)),
      300,
    );
    return () => clearTimeout(timer);
  }, [query]);
  return (
    <label className="work-field">
      <span>{label}</span>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Найти сотрудника, должность или подразделение"
      />
      {error && <small className="field-error">Справочник недоступен</small>}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Не выбрано</option>
        {items.map((x) => (
          <option key={x.id} value={x.id}>
            {x.display_name} · {x.target_type_label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function WorkHome({ navigate }: { navigate: Navigate }) {
  const [tasks, setTasks] = useState<Page<any> | null>(null);
  const [requests, setRequests] = useState<Page<any> | null>(null);
  useEffect(() => {
    tasksApi
      .list("page_size=5&ordering=-updated_at")
      .then(setTasks)
      .catch(() => undefined);
    requestsApi
      .list("page_size=5&ordering=-updated_at")
      .then(setRequests)
      .catch(() => undefined);
  }, []);
  return (
    <main className="work-page">
      <header className="work-title">
        <div>
          <p>Work Core</p>
          <h1>Рабочий центр</h1>
          <span>Производственные задачи и заявки</span>
        </div>
      </header>
      <div className="work-home-grid">
        <section className="work-card">
          <h2>Задачи</h2>
          <strong>{tasks?.count ?? "—"}</strong>
          <button onClick={() => navigate("/tasks")}>Открыть задачи</button>
        </section>
        <section className="work-card">
          <h2>Заявки</h2>
          <strong>{requests?.count ?? "—"}</strong>
          <button onClick={() => navigate("/requests")}>Открыть заявки</button>
        </section>
      </div>
    </main>
  );
}

function TaskList({ navigate }: { navigate: Navigate }) {
  const [page, setPage] = useState<Page<any> | null>(null);
  const [error, setError] = useState<any>();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [ordering, setOrdering] = useState("-updated_at");
  const [pageNo, setPageNo] = useState(1);
  const load = () => {
    const q = new URLSearchParams({
      page: String(pageNo),
      page_size: "20",
      ordering,
    });
    if (search) q.set("search", search);
    if (status) q.set("status", status);
    if (priority) q.set("priority", priority);
    setError(undefined);
    tasksApi.list(q.toString()).then(setPage).catch(setError);
  };
  useEffect(() => {
    const timer = setTimeout(load, 300);
    return () => clearTimeout(timer);
  }, [search, status, priority, ordering, pageNo]);
  return (
    <main className="work-page">
      <header className="work-title">
        <div>
          <p>Work Core</p>
          <h1>Задачи</h1>
          <span>Только production Tasks</span>
        </div>
        <button className="primary" onClick={() => navigate("/tasks/new")}>
          Создать задачу
        </button>
      </header>
      <div className="work-filters">
        <input
          aria-label="Поиск задач"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPageNo(1);
          }}
          placeholder="Номер, название или описание"
        />
        <select
          aria-label="Статус"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">Все статусы</option>
          {[
            "draft",
            "open",
            "in_progress",
            "waiting",
            "review",
            "completed",
            "cancelled",
          ].map((x) => (
            <option key={x} value={x}>
              {labels[x]}
            </option>
          ))}
        </select>
        <select
          aria-label="Приоритет"
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
        >
          <option value="">Все приоритеты</option>
          {["low", "normal", "high", "critical"].map((x) => (
            <option key={x} value={x}>
              {labels[x]}
            </option>
          ))}
        </select>
        <select
          aria-label="Сортировка"
          value={ordering}
          onChange={(e) => setOrdering(e.target.value)}
        >
          <option value="-updated_at">Недавно изменённые</option>
          <option value="due_at">Ближайший срок</option>
          <option value="number">По номеру</option>
        </select>
      </div>
      {error ? (
        <ErrorState error={error} onRetry={load} />
      ) : !page ? (
        <div className="work-loading">Загружаем задачи…</div>
      ) : !page.results.length ? (
        <div className="work-empty">
          <h2>Задач пока нет</h2>
          <p>Создайте первую задачу или измените фильтры.</p>
        </div>
      ) : (
        <>
          <div className="work-table task-grid">
            <b>Задача</b>
            <b>Статус</b>
            <b>Назначение</b>
            <b>Срок</b>
            {page.results.map((t) => (
              <React.Fragment key={t.id}>
                <button
                  className="work-object"
                  onClick={() => navigate(`/tasks/${t.id}`)}
                >
                  <strong>
                    {t.number} · {t.title}
                  </strong>
                  <small>
                    {labels[t.priority] || t.priority} · обновлено{" "}
                    {fmt(t.updated_at)}
                  </small>
                </button>
                <span className={`work-status ${t.status}`}>
                  {labels[t.status] || t.status}
                </span>
                <span>
                  <b>{person(t.responsible_employee)}</b>
                  <small>Исполнитель: {person(t.executor_employee)}</small>
                </span>
                <span className={t.is_overdue ? "overdue" : ""}>
                  {fmt(t.due_at)}
                </span>
              </React.Fragment>
            ))}
          </div>
          <Pager
            page={page}
            onPage={(d) => setPageNo((x) => Math.max(1, x + d))}
          />
        </>
      )}
    </main>
  );
}

function TaskCreate({ navigate }: { navigate: Navigate }) {
  const [form, setForm] = useState<any>({
    title: "",
    description: "",
    priority: "normal",
    responsible_target: "",
    executor_target: "",
    due_at: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<any>();
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(undefined);
    try {
      const data = {
        ...form,
        due_at: form.due_at ? new Date(form.due_at).toISOString() : null,
        responsible_target: form.responsible_target || null,
        executor_target: form.executor_target || null,
      };
      const task = await tasksApi.create(data);
      navigate(`/tasks/${task.id}`);
    } catch (x) {
      setError(x);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button
        className="work-drawer-scrim"
        aria-label="Закрыть создание задачи"
        onClick={() => navigate("/tasks")}
      />
      <main className="work-page narrow work-drawer">
      <button className="back" onClick={() => navigate("/tasks")}>
        ← К задачам
      </button>
      <header className="work-title">
        <div>
          <p>Новая задача</p>
          <h1>Создать задачу</h1>
        </div>
      </header>
      <form className="work-form" onSubmit={submit}>
        {error && <ErrorState error={error} />}
        <label className="work-field">
          <span>Название *</span>
          <input
            required
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </label>
        <label className="work-field">
          <span>Описание</span>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </label>
        <div className="form-row">
          <label className="work-field">
            <span>Приоритет</span>
            <select
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value })}
            >
              {["low", "normal", "high", "critical"].map((x) => (
                <option key={x} value={x}>
                  {labels[x]}
                </option>
              ))}
            </select>
          </label>
          <label className="work-field">
            <span>Срок</span>
            <input
              type="datetime-local"
              value={form.due_at}
              onChange={(e) => setForm({ ...form, due_at: e.target.value })}
            />
          </label>
        </div>
        <AssignmentSelector
          label="Ответственный target"
          value={form.responsible_target}
          onChange={(x) => setForm({ ...form, responsible_target: x })}
        />
        <AssignmentSelector
          label="Исполнитель target"
          value={form.executor_target}
          onChange={(x) => setForm({ ...form, executor_target: x })}
        />
        <button className="primary" disabled={busy}>
          {busy ? "Создаём…" : "Создать задачу"}
        </button>
      </form>
      </main>
    </>
  );
}

function ActionDialog({
  action,
  onCancel,
  onSubmit,
  busy,
}: {
  action: string;
  onCancel: () => void;
  onSubmit: (data: any) => void;
  busy: boolean;
}) {
  const [reason, setReason] = useState("");
  const [waitingReason, setWaitingReason] = useState("waiting_other");
  const [target, setTarget] = useState("");
  const [due, setDue] = useState("");
  const needsReason = [
    "reject",
    "reopen",
    "cancel",
    "pause",
    "wait_requester",
    "wait_external",
    "resolve",
    "reassign",
  ].includes(action);
  return (
    <div className="work-modal" role="dialog" aria-modal="true">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const data: any = {};
          if (needsReason)
            data[
              action === "resolve"
                ? "resolution_comment"
                : action.startsWith("wait_")
                  ? "comment"
                  : "reason"
            ] = reason;
          if (action === "pause") {
            data.reason = waitingReason;
            data.comment = reason;
          }
          if (action === "resolve") data.resolution_code = "RESOLVED";
          if (action === "reassign") {
            data.target = target;
            data.assignment_type = "responsible";
          }
          if (action === "change_deadline")
            data.due_at = new Date(due).toISOString();
          onSubmit(data);
        }}
      >
        <h2>{actionLabels[action] || action}</h2>
        {action === "reassign" && (
          <AssignmentSelector
            label="Новое назначение"
            value={target}
            onChange={setTarget}
          />
        )}{" "}
        {action === "change_deadline" && (
          <label className="work-field">
            <span>Новый срок</span>
            <input
              required
              type="datetime-local"
              value={due}
              onChange={(e) => setDue(e.target.value)}
            />
          </label>
        )}
        {action === "pause" && (
          <label className="work-field">
            <span>Причина ожидания</span>
            <select
              value={waitingReason}
              onChange={(e) => setWaitingReason(e.target.value)}
            >
              {[
                "waiting_requester",
                "waiting_external",
                "waiting_material",
                "waiting_approval",
                "waiting_other",
              ].map((value) => (
                <option key={value} value={value}>
                  {labels[value] || value}
                </option>
              ))}
            </select>
          </label>
        )}
        {needsReason && (
          <label className="work-field">
            <span>
              {action === "resolve" ? "Решение" : "Причина / комментарий"}
            </span>
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
        )}
        <div>
          <button type="button" onClick={onCancel}>
            Отмена
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "Выполняем…" : "Подтвердить"}
          </button>
        </div>
      </form>
    </div>
  );
}

function TaskDetail({ id, navigate }: { id: string; navigate: Navigate }) {
  const [task, setTask] = useState<any>();
  const [comments, setComments] = useState<any[]>([]);
  const [attachments, setAttachments] = useState<any[]>([]);
  const [watchers, setWatchers] = useState<any[]>([]);
  const [checklists, setChecklists] = useState<any[]>([]);
  const [activity, setActivity] = useState<any>();
  const [comment, setComment] = useState("");
  const [error, setError] = useState<any>();
  const [conflict, setConflict] = useState(false);
  const [action, setAction] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () =>
    Promise.all([
      tasksApi.get(id),
      tasksApi.comments(id),
      tasksApi.attachments(id),
      tasksApi.checklists(id),
      tasksApi.activity(id),
      tasksApi.watchers(id),
    ])
      .then(([a, b, c, d, e, f]) => {
        setTask(a);
        setComments(b);
        setAttachments(c);
        setChecklists(d);
        setActivity(e);
        setWatchers(f);
        setError(undefined);
      })
      .catch(setError);
  useEffect(() => {
    load();
  }, [id]);
  async function run(actionName: string, data: any = {}) {
    if (!task || busy) return;
    setBusy(true);
    try {
      const endpoint =
        actionName === "change_deadline"
          ? "deadline"
          : actionName.replace("wait_", "wait-");
      if (actionName === "watch") {
        await tasksApi.watch(id);
        setAction("");
        await load();
        return;
      }
      const updated = await tasksApi.action(id, endpoint, {
        version: task.version,
        ...data,
      });
      setTask(updated);
      setAction("");
      await load();
    } catch (x) {
      if (x instanceof WorkApiError && x.kind === "conflict") setConflict(true);
      else setError(x);
    } finally {
      setBusy(false);
    }
  }
  async function addComment(e: React.FormEvent) {
    e.preventDefault();
    if (!comment.trim() || busy) return;
    setBusy(true);
    try {
      await tasksApi.addComment(id, { body: comment });
      setComment("");
      setComments(await tasksApi.comments(id));
    } catch (x) {
      setError(x);
    } finally {
      setBusy(false);
    }
  }
  async function upload(file?: File) {
    if (!file) return;
    setBusy(true);
    try {
      await tasksApi.upload(id, file);
      setAttachments(await tasksApi.attachments(id));
    } catch (x) {
      setError(x);
    } finally {
      setBusy(false);
    }
  }
  if (error && !task)
    return (
      <main className="work-page">
        <ErrorState error={error} onRetry={load} />
      </main>
    );
  if (!task)
    return (
      <main className="work-page">
        <div className="work-loading">Загружаем задачу…</div>
      </main>
    );
  return (
    <main className="work-page">
      <button className="back" onClick={() => navigate("/tasks")}>
        ← К задачам
      </button>
      <header className="work-detail-head">
        <div>
          <p>{task.number}</p>
          <h1>{task.title}</h1>
          <div>
            <span className={`work-status ${task.status}`}>
              {labels[task.status] || task.status}
            </span>
            <span>{labels[task.priority] || task.priority}</span>
          </div>
        </div>
        <div className="work-actions">
          {(task.available_actions || [])
            .filter(
              (x: string) =>
                ![
                  "edit",
                  "comment",
                  "attachment_add",
                  "watcher_manage",
                  "checklist_manage",
                ].includes(x),
            )
            .map((x: string) => (
              <button
                key={x}
                disabled={busy}
                onClick={() =>
                  ["publish", "start", "resume", "complete", "accept"].includes(
                    x,
                  )
                    ? run(x)
                    : setAction(x)
                }
              >
                {actionLabels[x] || x}
              </button>
            ))}
        </div>
      </header>
      {error && <ErrorState error={error} />}{" "}
      {conflict && (
        <div className="conflict" role="alert">
          <b>Задача была изменена другим пользователем.</b>
          <span>Обновите данные и повторите действие.</span>
          <button
            onClick={() => {
              setConflict(false);
              load();
            }}
          >
            Обновить
          </button>
        </div>
      )}
      <div className="work-detail-grid">
        <section className="work-card">
          <h2>Основная информация</h2>
          <dl>
            <div>
              <dt>Ответственный target</dt>
              <dd>
                {task.responsible_target_display ||
                  person(task.responsible_target)}
              </dd>
            </div>
            <div>
              <dt>Фактический ответственный</dt>
              <dd>
                {task.responsible_employee_display ||
                  person(task.responsible_employee)}
              </dd>
            </div>
            <div>
              <dt>Исполнитель target</dt>
              <dd>
                {task.executor_target_display || person(task.executor_target)}
              </dd>
            </div>
            <div>
              <dt>Фактический исполнитель</dt>
              <dd>
                {task.executor_employee_display ||
                  person(task.executor_employee)}
              </dd>
            </div>
            <div>
              <dt>Срок</dt>
              <dd className={task.is_overdue ? "overdue" : ""}>
                {fmt(task.due_at)}
              </dd>
            </div>
            <div>
              <dt>Версия</dt>
              <dd>{task.version}</dd>
            </div>
          </dl>
          <p className="description">
            {task.description || "Описание не добавлено."}
          </p>
        </section>
        <section className="work-card">
          <h2>
            Чек-листы · {task.checklist_progress?.completed || 0}/
            {task.checklist_progress?.total || 0}
          </h2>
          {checklists.length ? (
            checklists.map((c) => (
              <div key={c.id} className="checklist">
                <b>{c.name}</b>
                {c.items.map((i: any) => (
                  <label key={i.id}>
                    <input
                      type="checkbox"
                      checked={i.is_completed}
                      disabled={busy}
                      onChange={async () => {
                        await tasksApi.toggleItem(
                          id,
                          c.id,
                          i.id,
                          !i.is_completed,
                        );
                        setChecklists(await tasksApi.checklists(id));
                      }}
                    />
                    {i.text}
                    {i.required && <em>*</em>}
                  </label>
                ))}
              </div>
            ))
          ) : (
            <p className="muted">Чек-листов нет.</p>
          )}
        </section>
        <section className="work-card">
          <h2>Комментарии</h2>
          <form className="comment-form" onSubmit={addComment}>
            <textarea
              aria-label="Новый комментарий"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Написать комментарий"
            />
            <button disabled={busy || !comment.trim()}>Отправить</button>
          </form>
          {comments.map((c) => (
            <article className="comment" key={c.id}>
              <b>{c.author_display || person(c.author)}</b>
              {c.is_internal && <em>Внутренний</em>}
              <p>{c.body}</p>
              <small>{fmt(c.created_at)}</small>
            </article>
          ))}
        </section>
        <section className="work-card">
          <h2>Вложения</h2>
          <label className="upload">
            {busy ? "Загрузка…" : "Прикрепить файл"}
            <input
              type="file"
              disabled={busy}
              onChange={(e) => upload(e.target.files?.[0])}
            />
          </label>
          {attachments.map((a) => (
            <div className="attachment" key={a.id}>
              <button
                className="link-button"
                onClick={() =>
                  tasksApi
                    .download(id, a.id, a.original_filename)
                    .catch(setError)
                }
              >
                {a.original_filename}
              </button>
              <span>
                {Math.ceil(a.size / 1024)} КБ · {fmt(a.created_at)}
              </span>
            </div>
          ))}
        </section>
        <section className="work-card">
          <h2>Наблюдатели</h2>
          {watchers.length ? (
            watchers.map((watcher) => (
              <div className="person-row" key={watcher.id}>
                {watcher.employee_display || person(watcher.employee)}
              </div>
            ))
          ) : (
            <p className="muted">Наблюдателей нет.</p>
          )}
        </section>
        <section className="work-card wide">
          <h2>Активность</h2>
          {(activity?.results || activity?.items || []).map(
            (a: any, i: number) => (
              <div className="timeline" key={a.id || i}>
                <b>{a.title || a.action || a.type}</b>
                <span>{a.description || a.message}</span>
                <small>{fmt(a.created_at)}</small>
              </div>
            ),
          )}
        </section>
      </div>
      {action &&
        !["publish", "start", "resume", "complete", "accept"].includes(
          action,
        ) && (
          <ActionDialog
            action={action}
            busy={busy}
            onCancel={() => setAction("")}
            onSubmit={(data) => run(action, data)}
          />
        )}
    </main>
  );
}

function flattenCatalog(nodes: any[], out: any[] = []) {
  for (const node of nodes) {
    for (const service of node.services || [])
      for (const rt of service.request_types || [])
        out.push({
          ...rt,
          service_name: service.name,
          category_name: node.name,
        });
    flattenCatalog(node.children || [], out);
  }
  return out;
}
function DynamicField({
  field,
  value,
  onChange,
  lookups,
}: {
  field: any;
  value: any;
  onChange: (v: any) => void;
  lookups: Record<string, any[]>;
}) {
  const type = String(field.field_type).toLowerCase();
  const common = { id: `field-${field.key}` };
  if (type === "textarea")
    return (
      <textarea
        {...common}
        required={field.required}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  if (type === "boolean")
    return (
      <input
        {...common}
        type="checkbox"
        checked={Boolean(value)}
        onChange={(e) => onChange(e.target.checked)}
      />
    );
  if (type === "choice")
    return (
      <select
        {...common}
        required={field.required}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Выберите</option>
        {field.options.map((o: any) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    );
  if (type === "multi_choice")
    return (
      <select
        {...common}
        multiple
        required={field.required}
        value={value || []}
        onChange={(e) =>
          onChange(Array.from(e.target.selectedOptions, (x) => x.value))
        }
      >
        {field.options.map((o: any) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    );
  if (["employee", "org_unit", "legal_entity", "location"].includes(type))
    return (
      <select
        {...common}
        required={field.required}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Выберите</option>
        {(lookups[type] || []).map((x) => (
          <option key={x.id} value={x.id}>
            {x.display_name || x.name}
          </option>
        ))}
      </select>
    );
  if (type === "file")
    return (
      <input
        {...common}
        type="file"
        required={field.required}
        onChange={(e) => onChange(e.target.files?.[0] || null)}
      />
    );
  const htmlType: { [k: string]: string } = {
    integer: "number",
    decimal: "number",
    date: "date",
    datetime: "datetime-local",
  };
  return (
    <input
      {...common}
      type={htmlType[type] || "text"}
      step={type === "decimal" ? "any" : undefined}
      required={field.required}
      value={value ?? ""}
      onChange={(e) =>
        onChange(
          type === "integer"
            ? Number(e.target.value)
            : type === "datetime" && e.target.value
              ? new Date(e.target.value).toISOString()
              : e.target.value,
        )
      }
    />
  );
}

function RequestList({ navigate }: { navigate: Navigate }) {
  const [page, setPage] = useState<Page<any> | null>(null);
  const [error, setError] = useState<any>();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [pageNo, setPageNo] = useState(1);
  const load = () => {
    const q = new URLSearchParams({
      page: String(pageNo),
      page_size: "20",
      ordering: "-updated_at",
    });
    if (search) q.set("search", search);
    if (status) q.set("status", status);
    if (priority) q.set("priority", priority);
    requestsApi.list(q.toString()).then(setPage).catch(setError);
  };
  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [search, status, priority, pageNo]);
  return (
    <main className="work-page">
      <header className="work-title">
        <div>
          <p>Каталог услуг</p>
          <h1>Заявки</h1>
          <span>Production Service Requests</span>
        </div>
        <button className="primary" onClick={() => navigate("/requests/new")}>
          Создать заявку
        </button>
      </header>
      <div className="work-filters">
        <input
          aria-label="Поиск заявок"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="REQ, тема или описание"
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Все статусы</option>
          {[
            "new",
            "assigned",
            "in_progress",
            "waiting_requester",
            "waiting_external",
            "resolved",
            "closed",
            "cancelled",
          ].map((x) => (
            <option key={x} value={x}>
              {labels[x]}
            </option>
          ))}
        </select>
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">Все приоритеты</option>
          {["low", "normal", "high", "critical"].map((x) => (
            <option key={x} value={x}>
              {labels[x]}
            </option>
          ))}
        </select>
      </div>
      {error ? (
        <ErrorState error={error} onRetry={load} />
      ) : !page ? (
        <div className="work-loading">Загружаем заявки…</div>
      ) : !page.results.length ? (
        <div className="work-empty">
          <h2>Заявок пока нет</h2>
          <p>Выберите услугу и создайте обращение.</p>
        </div>
      ) : (
        <>
          <div className="work-table request-grid">
            <b>Заявка</b>
            <b>Статус</b>
            <b>Исполнитель</b>
            <b>SLA / обновление</b>
            {page.results.map((r) => (
              <React.Fragment key={r.id}>
                <button
                  className="work-object"
                  onClick={() => navigate(`/requests/${r.id}`)}
                >
                  <strong>
                    {r.number} · {r.subject}
                  </strong>
                  <small>{r.request_type_name}</small>
                </button>
                <span className={`work-status ${r.status}`}>
                  {labels[r.status] || r.status}
                </span>
                <span>
                  {r.assigned_employee_display || person(r.assigned_employee)}
                </span>
                <span>
                  <b>
                    {r.sla?.has_sla
                      ? r.sla.resolution_status || "Активен"
                      : "Без SLA"}
                  </b>
                  <small>{fmt(r.updated_at)}</small>
                </span>
              </React.Fragment>
            ))}
          </div>
          <Pager
            page={page}
            onPage={(d) => setPageNo((x) => Math.max(1, x + d))}
          />
        </>
      )}
    </main>
  );
}

function RequestCreate({ navigate }: { navigate: Navigate }) {
  const [catalog, setCatalog] = useState<any[]>([]);
  const [typeId, setTypeId] = useState("");
  const [schema, setSchema] = useState<any>();
  const [form, setForm] = useState<any>({
    subject: "",
    description: "",
    priority: "normal",
    payload: {},
  });
  const [lookups, setLookups] = useState<Record<string, any[]>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<any>();
  useEffect(() => {
    requestsApi
      .catalog()
      .then((x) => setCatalog(flattenCatalog(x)))
      .catch(setError);
  }, []);
  useEffect(() => {
    if (!typeId) return;
    requestsApi.schema(typeId).then(setSchema).catch(setError);
  }, [typeId]);
  useEffect(() => {
    if (!schema) return;
    const types = new Set(schema.fields.map((x: any) => x.field_type));
    Promise.all([
      types.has("employee") ? lookupApi.employees() : null,
      types.has("org_unit") ? lookupApi.orgUnits() : null,
      types.has("legal_entity") ? lookupApi.legalEntities() : null,
      types.has("location") ? lookupApi.locations() : null,
    ])
      .then(([a, b, c, d]) =>
        setLookups({
          employee: a?.results || [],
          org_unit: b?.results || [],
          legal_entity: c?.results || [],
          location: d?.results || [],
        }),
      )
      .catch(setError);
  }, [schema]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const files: { field: any; file: File }[] = [];
      const payload: any = {};
      for (const field of schema.fields) {
        const value = form.payload[field.key];
        if (value instanceof File) {
          files.push({ field, file: value });
          payload[field.key] = value.name;
        } else if (value !== "" && value !== undefined)
          payload[field.key] = value;
      }
      const request = await requestsApi.create({
        request_type: typeId,
        subject: form.subject,
        description: form.description,
        priority: form.priority,
        payload,
      });
      for (const x of files)
        await requestsApi.upload(request.id, x.file, "public");
      navigate(`/requests/${request.id}`);
    } catch (x) {
      setError(x);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button
        className="work-drawer-scrim"
        aria-label="Закрыть создание заявки"
        onClick={() => navigate("/requests")}
      />
      <main className="work-page narrow work-drawer">
      <button className="back" onClick={() => navigate("/requests")}>
        ← К заявкам
      </button>
      <header className="work-title">
        <div>
          <p>Каталог услуг</p>
          <h1>Создать заявку</h1>
        </div>
      </header>
      <form className="work-form" onSubmit={submit}>
        {error && <ErrorState error={error} />}
        <label className="work-field">
          <span>Тип заявки *</span>
          <select
            required
            value={typeId}
            onChange={(e) => setTypeId(e.target.value)}
          >
            <option value="">Выберите услугу</option>
            {catalog.map((x) => (
              <option key={x.id} value={x.id}>
                {x.category_name} · {x.service_name} · {x.name}
              </option>
            ))}
          </select>
        </label>
        {schema && (
          <>
            <label className="work-field">
              <span>Тема *</span>
              <input
                required
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
              />
            </label>
            <label className="work-field">
              <span>Описание</span>
              <textarea
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
              />
            </label>
            <label className="work-field">
              <span>Приоритет</span>
              <select
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value })}
              >
                {["low", "normal", "high", "critical"].map((x) => (
                  <option key={x} value={x}>
                    {labels[x]}
                  </option>
                ))}
              </select>
            </label>
            {schema.fields
              .sort((a: any, b: any) => a.position - b.position)
              .map((field: any) => {
                const condition = field.config?.visible_if;
                if (condition) {
                  const equal =
                    form.payload[condition.field] === condition.value;
                  const visible =
                    condition.operator === "EQUALS" ? equal : !equal;
                  if (!visible) return null;
                }
                return (
                  <label
                    className="work-field"
                    key={field.key}
                    htmlFor={`field-${field.key}`}
                  >
                    <span>
                      {field.label}
                      {field.required && " *"}
                    </span>
                    <DynamicField
                      field={field}
                      value={form.payload[field.key]}
                      lookups={lookups}
                      onChange={(v) =>
                        setForm({
                          ...form,
                          payload: { ...form.payload, [field.key]: v },
                        })
                      }
                    />
                    {field.help_text && <small>{field.help_text}</small>}
                    {(error as WorkApiError)?.fields?.[field.key]?.map((x) => (
                      <small className="field-error" key={x}>
                        {x}
                      </small>
                    ))}
                  </label>
                );
              })}
            <button className="primary" disabled={busy}>
              {busy ? "Отправляем…" : "Создать заявку"}
            </button>
          </>
        )}
      </form>
      </main>
    </>
  );
}

function RequestDetail({ id, navigate }: { id: string; navigate: Navigate }) {
  const [item, setItem] = useState<any>();
  const [comments, setComments] = useState<any[]>([]);
  const [attachments, setAttachments] = useState<any[]>([]);
  const [watchers, setWatchers] = useState<any[]>([]);
  const [activity, setActivity] = useState<any>();
  const [history, setHistory] = useState<any>();
  const [sla, setSla] = useState<any>();
  const [comment, setComment] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [error, setError] = useState<any>();
  const [conflict, setConflict] = useState(false);
  const [action, setAction] = useState("");
  const [busy, setBusy] = useState(false);
  const [taskDraft, setTaskDraft] = useState({
    title: "",
    responsible_target: "",
    due_at: "",
  });
  const load = () =>
    Promise.all([
      requestsApi.get(id),
      requestsApi.comments(id),
      requestsApi.attachments(id),
      requestsApi.activity(id),
      requestsApi.history(id),
      requestsApi.sla(id),
      requestsApi.watchers(id),
    ])
      .then(([a, b, c, d, e, f, g]) => {
        setItem(a);
        setComments(b);
        setAttachments(c);
        setActivity(d);
        setHistory(e);
        setSla(f);
        setWatchers(g);
        setError(undefined);
      })
      .catch(setError);
  useEffect(() => {
    load();
  }, [id]);
  async function run(actionName: string, data: any = {}) {
    if (!item || busy) return;
    setBusy(true);
    try {
      const endpoint = actionName.replace("wait_", "wait-");
      if (actionName === "watch" || actionName === "unwatch") {
        await requestsApi.watch(id, actionName === "unwatch");
        setAction("");
        await load();
        return;
      }
      const updated = await requestsApi.action(id, endpoint, {
        version: item.version,
        ...data,
      });
      setItem(updated);
      setAction("");
      await load();
    } catch (x) {
      if (x instanceof WorkApiError && x.kind === "conflict") setConflict(true);
      else setError(x);
    } finally {
      setBusy(false);
    }
  }
  async function addComment(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await requestsApi.addComment(id, { body: comment, visibility });
      setComment("");
      setComments(await requestsApi.comments(id));
    } catch (x) {
      setError(x);
    } finally {
      setBusy(false);
    }
  }
  async function upload(file?: File) {
    if (!file) return;
    setBusy(true);
    try {
      await requestsApi.upload(id, file, visibility);
      setAttachments(await requestsApi.attachments(id));
    } catch (x) {
      setError(x);
    } finally {
      setBusy(false);
    }
  }
  async function createExecutionTask(event: React.FormEvent) {
    event.preventDefault();
    if (!taskDraft.title.trim() || !taskDraft.responsible_target || busy)
      return;
    setBusy(true);
    try {
      const created = await requestsApi.createTask(id, {
        version: item.version,
        relation_type: "execution",
        title: taskDraft.title,
        responsible_target: taskDraft.responsible_target,
        ...(taskDraft.due_at
          ? { due_at: new Date(taskDraft.due_at).toISOString() }
          : {}),
      });
      setTaskDraft({ title: "", responsible_target: "", due_at: "" });
      await load();
      navigate(`/tasks/${created.id}`);
    } catch (x) {
      if (x instanceof WorkApiError && x.kind === "conflict") setConflict(true);
      else setError(x);
    } finally {
      setBusy(false);
    }
  }
  if (error && !item)
    return (
      <main className="work-page">
        <ErrorState error={error} onRetry={load} />
      </main>
    );
  if (!item)
    return (
      <main className="work-page">
        <div className="work-loading">Загружаем заявку…</div>
      </main>
    );
  const internalAllowed =
    (item.available_actions || []).includes("comment_internal") ||
    (item.available_actions || []).includes("attachment_internal");
  return (
    <main className="work-page">
      <button className="back" onClick={() => navigate("/requests")}>
        ← К заявкам
      </button>
      <header className="work-detail-head">
        <div>
          <p>
            {item.number} · {item.request_type_name}
          </p>
          <h1>{item.subject}</h1>
          <div>
            <span className={`work-status ${item.status}`}>
              {labels[item.status] || item.status}
            </span>
            <span>{labels[item.priority] || item.priority}</span>
          </div>
        </div>
        <div className="work-actions">
          {(item.available_actions || [])
            .filter(
              (x: string) =>
                ![
                  "comment",
                  "comment_internal",
                  "attachment_add",
                  "attachment_internal",
                  "watcher_manage",
                  "task_create",
                ].includes(x),
            )
            .map((x: string) => (
              <button
                key={x}
                disabled={busy}
                onClick={() =>
                  ["start", "resume", "close", "watch", "unwatch"].includes(x)
                    ? run(x)
                    : setAction(x)
                }
              >
                {actionLabels[x] || x}
              </button>
            ))}
        </div>
      </header>
      {error && <ErrorState error={error} />}{" "}
      {conflict && (
        <div className="conflict">
          <b>Заявка была изменена другим пользователем.</b>
          <span>Обновите данные и повторите действие.</span>
          <button
            onClick={() => {
              setConflict(false);
              load();
            }}
          >
            Обновить
          </button>
        </div>
      )}
      <div className="work-detail-grid">
        <section className="work-card">
          <h2>Данные заявки</h2>
          <dl>
            <div>
              <dt>Заявитель</dt>
              <dd>{item.requester_display || person(item.requester)}</dd>
            </div>
            <div>
              <dt>Назначение</dt>
              <dd>
                {item.assigned_target_display || person(item.assigned_target)}
              </dd>
            </div>
            <div>
              <dt>Фактический исполнитель</dt>
              <dd>
                {item.assigned_employee_display ||
                  person(item.assigned_employee)}
              </dd>
            </div>
            <div>
              <dt>Создана</dt>
              <dd>{fmt(item.created_at)}</dd>
            </div>
            <div>
              <dt>Версия</dt>
              <dd>{item.version}</dd>
            </div>
          </dl>
          <p className="description">
            {item.description || "Описание не добавлено."}
          </p>
          {item.dynamic_values?.map((v: any) => (
            <div className="dynamic-value" key={v.id}>
              <b>{v.label}</b>
              <span>
                {Array.isArray(v.value)
                  ? v.value.join(", ")
                  : String(v.value ?? "—")}
              </span>
            </div>
          ))}
        </section>
        <section
          className={`work-card sla-card ${item.sla?.resolution_status || ""}`}
        >
          <h2>SLA</h2>
          {sla?.has_sla ? (
            <>
              <dl>
                <div>
                  <dt>Состояние</dt>
                  <dd>{sla.status}</dd>
                </div>
                <div>
                  <dt>Response</dt>
                  <dd>{item.sla.response_status || "—"}</dd>
                </div>
                <div>
                  <dt>Resolution</dt>
                  <dd>{item.sla.resolution_status || "—"}</dd>
                </div>
                <div>
                  <dt>Срок решения</dt>
                  <dd>{fmt(item.sla.resolution_due_at)}</dd>
                </div>
              </dl>
              {sla.resolution_cycles?.map((x: any) => (
                <div key={x.id} className="sla-cycle">
                  Цикл {x.cycle_number}: {fmt(x.started_at)} →{" "}
                  {fmt(x.achieved_at || x.due_at)}
                </div>
              ))}
            </>
          ) : (
            <p>Для заявки SLA не назначен.</p>
          )}
        </section>
        <section className="work-card">
          <h2>Комментарии</h2>
          {internalAllowed && (
            <div className="visibility-switch">
              <button
                className={visibility === "public" ? "active" : ""}
                onClick={() => setVisibility("public")}
              >
                Публичный
              </button>
              <button
                className={visibility === "internal" ? "active" : ""}
                onClick={() => setVisibility("internal")}
              >
                Внутренний
              </button>
            </div>
          )}
          <form className="comment-form" onSubmit={addComment}>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Добавить комментарий"
            />
            <button disabled={busy || !comment.trim()}>Отправить</button>
          </form>
          {comments.map((c) => (
            <article className={`comment ${c.visibility}`} key={c.id}>
              <b>{c.author_display || person(c.author)}</b>
              <em>
                {c.visibility === "internal" ? "Внутренний" : "Публичный"}
              </em>
              <p>{c.body}</p>
              <small>{fmt(c.created_at)}</small>
            </article>
          ))}
        </section>
        <section className="work-card">
          <h2>Вложения</h2>
          <label className="upload">
            {busy
              ? "Загрузка…"
              : `Добавить ${visibility === "internal" ? "внутренний" : "публичный"} файл`}
            <input
              type="file"
              disabled={busy}
              onChange={(e) => upload(e.target.files?.[0])}
            />
          </label>
          {attachments.map((a) => (
            <div className="attachment" key={a.id}>
              <button
                className="link-button"
                onClick={() =>
                  requestsApi
                    .download(id, a.id, a.original_filename)
                    .catch(setError)
                }
              >
                {a.original_filename}
              </button>
              <em>{a.visibility}</em>
              <span>
                {Math.ceil(a.size / 1024)} КБ · {fmt(a.created_at)}
              </span>
            </div>
          ))}
        </section>
        <section className="work-card">
          <h2>Наблюдатели</h2>
          {watchers.length ? (
            watchers.map((watcher) => (
              <div className="person-row" key={watcher.id}>
                {watcher.employee_display || person(watcher.employee)}
              </div>
            ))
          ) : (
            <p className="muted">Наблюдателей нет.</p>
          )}
        </section>
        <section className="work-card">
          <h2>Связанные задачи</h2>
          {(item.available_actions || []).includes("task_create") && (
            <form className="embedded-form" onSubmit={createExecutionTask}>
              <label className="work-field">
                <span>Новая исполнительная задача</span>
                <input
                  required
                  value={taskDraft.title}
                  onChange={(e) =>
                    setTaskDraft({ ...taskDraft, title: e.target.value })
                  }
                  placeholder="Название задачи"
                />
              </label>
              <AssignmentSelector
                label="Ответственный"
                value={taskDraft.responsible_target}
                onChange={(value) =>
                  setTaskDraft({ ...taskDraft, responsible_target: value })
                }
              />
              <label className="work-field">
                <span>Срок</span>
                <input
                  type="datetime-local"
                  value={taskDraft.due_at}
                  onChange={(e) =>
                    setTaskDraft({ ...taskDraft, due_at: e.target.value })
                  }
                />
              </label>
              <button disabled={busy || !taskDraft.responsible_target}>
                Создать задачу
              </button>
            </form>
          )}
          {item.tasks?.length ? (
            item.tasks.map((x: any) => (
              <button
                className="linked-task"
                key={x.id}
                onClick={() => navigate(`/tasks/${x.task}`)}
              >
                {x.number} · {x.title}
                <span>{labels[x.status] || x.status}</span>
              </button>
            ))
          ) : (
            <p>Исполнительных задач нет.</p>
          )}
          <small>
            Политика выполнения: {item.tasks_summary?.completed || 0} завершено
            из {item.tasks_summary?.total || 0}
          </small>
        </section>
        <section className="work-card wide">
          <h2>История и активность</h2>
          {history?.status?.map((x: any, i: number) => (
            <div className="timeline" key={i}>
              <b>
                {labels[x.from_status] || x.from_status || "Создание"} →{" "}
                {labels[x.to_status] || x.to_status}
              </b>
              <span>{x.reason}</span>
              <small>{fmt(x.created_at)}</small>
            </div>
          ))}
          {(activity?.results || activity?.items || []).map(
            (x: any, i: number) => (
              <div className="timeline" key={x.id || i}>
                <b>{x.title || x.action || x.type}</b>
                <span>{x.description || x.message}</span>
                <small>{fmt(x.created_at)}</small>
              </div>
            ),
          )}
        </section>
      </div>
      {action &&
        !["start", "resume", "close", "watch", "unwatch"].includes(action) && (
          <ActionDialog
            action={action}
            busy={busy}
            onCancel={() => setAction("")}
            onSubmit={(data) => run(action, data)}
          />
        )}
    </main>
  );
}

export function ProductionWorkRouter({
  path,
  navigate,
}: {
  path: string;
  navigate: Navigate;
}) {
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "tasks") {
    if (parts[1] === "new") return <TaskCreate navigate={navigate} />;
    if (parts[1]) return <TaskDetail id={parts[1]} navigate={navigate} />;
    return <TaskList navigate={navigate} />;
  }
  if (parts[0] === "requests") {
    if (parts[1] === "new") return <RequestCreate navigate={navigate} />;
    if (parts[1]) return <RequestDetail id={parts[1]} navigate={navigate} />;
    return <RequestList navigate={navigate} />;
  }
  return <WorkHome navigate={navigate} />;
}
