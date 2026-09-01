import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Bell,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  Search,
  Settings,
  ShieldCheck,
  Users,
  Wrench,
  Paperclip,
  Download,
  BookOpen,
  Star,
  FileText,
  Clock3,
  ArrowLeft,
  Eye,
  GraduationCap,
  PlayCircle,
  Award,
  CircleCheckBig,
  X,
} from "lucide-react";
import "./styles.css";
import "./tasks.css";
import "./navigation.css";
import "./checklists.css";
import "./sensors.css";
import "./incidents.css";
import "./analytics.css";
import "./notifications.css";
import "./knowledge.css";
import "./learning.css";
import { ProductionWorkRouter, WorkHome } from "./work";
import { ActivationPage, PeopleRouter, RegistrationPage } from "./people";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
const APP_VERSION = import.meta.env.VITE_APP_VERSION || "1.0.0-rc1";
const INTERNAL_API = API.replace(/\/api\/v1\/?$/, "/api/internal/v1");
type Profile = {
  id: number;
  full_name: string;
  email: string;
  roles: { code: string; name: string }[];
  employee: {
    id: number;
    position: string;
    department: string;
    company: string;
    employee_number: string;
  } | null;
  is_demo: boolean;
};
type TaskData = {
  id: number;
  title: string;
  assignee: { id: number; full_name: string };
  creator: { id: number; full_name: string };
  facility_name: string;
  category: string;
  priority: string;
  priority_label: string;
  status: string;
  status_label: string;
  deadline: string;
  is_overdue: boolean;
  description?: string;
  acceptance_criteria?: string;
  result_text?: string;
  comments?: {
    id: number;
    author: { full_name: string };
    text: string;
    created_at: string;
  }[];
  attachments?: {
    id: number;
    uploader: { full_name: string };
    original_name: string;
    content_type: string;
    size: number;
    created_at: string;
  }[];
  recurrence?: {
    frequency: string;
    interval: number;
    next_run_at: string;
    is_active: boolean;
  } | null;
  history?: {
    id: number;
    actor: { full_name: string };
    action: string;
    from_status: string;
    to_status: string;
    created_at: string;
  }[];
};
type DashboardData = {
  counts: {
    active: number;
    today: number;
    overdue: number;
    high_priority: number;
    on_review: number;
  };
  today_tasks: TaskData[];
  by_status: { status: string; label: string; count: number }[];
  facilities: { id: number; name: string; address: string; status: string }[];
};
type ChecklistQuestionData = {
  id: number;
  text: string;
  question_type: string;
  type_label: string;
  is_required: boolean;
  requires_photo: boolean;
  min_value: string | null;
  max_value: string | null;
};
type ChecklistRunData = {
  id: number;
  template: {
    name: string;
    category: string;
    description: string;
    is_haccp: boolean;
    questions: ChecklistQuestionData[];
  };
  facility_name: string;
  due_at: string;
  status: string;
  status_label: string;
  score: string | null;
  violations: { id: number; description: string; task_id: number }[];
};
type SensorData = {
  id: number;
  name: string;
  serial_number: string;
  type_label: string;
  facility_name: string;
  zone_name: string;
  unit: string;
  allowed_min: string;
  allowed_max: string;
  critical_min: string;
  critical_max: string;
  battery_level: number;
  signal_quality: number;
  state: string;
  state_label: string;
  last_reading_at: string;
  latest: { value: string; level: string; recorded_at: string } | null;
  readings?: { value: string; level: string; recorded_at: string }[];
  events?: {
    id: number;
    level: string;
    started_at: string;
    ended_at: string | null;
    peak_value: string;
  }[];
};
type IncidentData = {
  id: number;
  sensor_name: string;
  facility_name: string;
  zone_name: string;
  unit: string;
  deviation_type: string;
  level: string;
  started_at: string;
  detected_at: string;
  peak_value: string;
  status: string;
  status_label: string;
  response_seconds: number | null;
  response_run_id: number | null;
  task_id: number | null;
  history: {
    id: number;
    actor_name: string;
    action: string;
    created_at: string;
  }[];
};
type PerformanceData = {
  full_name: string;
  position: string;
  department: string;
  score: number;
  timeliness: number;
  quality: number;
  checklist_score: number;
  response_score: number;
  avg_response_seconds: number | null;
  active_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  returned_tasks: number;
};
type ManagementData = {
  company: { id: number; name: string };
  summary: {
    employee_count: number;
    average_score: number;
    active_tasks: number;
    overdue_tasks: number;
    open_incidents: number;
  };
  employees: (PerformanceData & { employee_id: number })[];
  facilities: {
    id: number;
    name: string;
    active_tasks: number;
    open_incidents: number;
    checklist_score: number;
  }[];
};
type NotificationData = {
  id: number;
  type_label: string;
  priority: string;
  title: string;
  message: string;
  entity_type: string;
  entity_id: string | null;
  action_url: string;
  is_read: boolean;
  telegram_status: string;
  created_at: string;
};
type ChannelStatus = {
  telegram: {
    available: boolean;
    linked: boolean;
    username: string;
    linked_at: string | null;
  };
  email: { available: boolean; address_masked: string };
  in_app: { available: boolean };
};
type MaterialVersionData = {
  id: number;
  version: number;
  title: string;
  description: string;
  original_name: string;
  size: number;
  external_url: string;
  content: string;
  change_summary: string;
  created_at: string;
  effective_from: string | null;
  is_current: boolean;
  download_url: string | null;
};
type KnowledgeMaterialData = {
  id: number;
  title: string;
  description: string;
  material_type: string;
  material_type_label: string;
  category: number;
  category_name: string;
  status: string;
  is_required: boolean;
  is_downloadable: boolean;
  is_featured: boolean;
  is_favorite: boolean;
  published_at: string | null;
  updated_at: string;
  current_version: MaterialVersionData | null;
  versions?: MaterialVersionData[];
  tags: { id: number; name: string; slug: string }[];
};
type KnowledgeCategoryData = {
  id: number;
  name: string;
  parent: number | null;
};
type AcknowledgmentData = {
  id: number;
  material_id: number;
  material_title: string;
  version_number: number;
  status: string;
  due_at: string | null;
};
type LessonData = {
  id: number;
  title: string;
  lesson_type: string;
  lesson_type_label: string;
  content: string;
  video_url: string;
  estimated_duration_minutes: number;
  sort_order: number;
  is_required: boolean;
  requires_confirmation: boolean;
};
type CourseModuleData = {
  id: number;
  title: string;
  description: string;
  sort_order: number;
  lessons: LessonData[];
};
type CourseData = {
  id: number;
  title: string;
  short_description: string;
  description?: string;
  category_name: string;
  is_mandatory: boolean;
  estimated_duration_minutes: number;
  passing_score: number;
  max_attempts: number;
  certificate_enabled: boolean;
  status: string;
  modules_count: number;
  lessons_count: number;
  modules?: CourseModuleData[];
};
type AssignmentData = {
  id: number;
  course: number;
  course_title: string;
  status: string;
  status_label: string;
  progress_percent: number;
  current_lesson: number | null;
  is_mandatory: boolean;
  due_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  lesson_progress: {
    lesson: number;
    completed_at: string | null;
    confirmed: boolean;
  }[];
};
type AssessmentData = {
  id: number;
  course: number;
  title: string;
  description: string;
  time_limit_minutes: number;
  passing_score: number;
  max_attempts: number;
  questions_count: number;
};
type AttemptData = {
  id: number;
  assessment: number;
  assessment_title: string;
  status: string;
  score_percent: string;
  passed: boolean;
  attempt_number: number;
  questions: {
    id: number;
    text: string;
    question_type: string;
    is_required: boolean;
    options: { id: number; text: string }[];
  }[];
  responses: {
    id: number;
    question: number;
    is_correct: boolean | null;
    points_awarded: string;
  }[];
};
type CertificateData = {
  id: number;
  course_title: string;
  certificate_number: string;
  issued_at: string;
  expires_at: string | null;
  status: string;
  verification_code: string;
};
type ProductionMetric = {
  value: number | null;
  sample_size: number;
  status: string;
  explanation: { population?: string; source_facts?: number };
};
type ProductionPerformance = {
  employee: { id: string; name: string; position: string };
  period: { from: string; to: string; timezone: string; semantics: string };
  calculation_version: string;
  metrics: Record<string, ProductionMetric>;
  previous_period: Record<string, ProductionMetric>;
};
async function api(path: string, options: RequestInit = {}) {
  const token = sessionStorage.getItem("access");
  const r = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(JSON.stringify(d));
  }
  return r.json();
}
async function upload(path: string, file: File) {
  const token = sessionStorage.getItem("access");
  const body = new FormData();
  body.append("file", file);
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
async function downloadAttachment(
  taskId: number,
  attachment: { id: number; original_name: string },
) {
  const token = sessionStorage.getItem("access");
  const r = await fetch(
    `${API}/tasks/${taskId}/attachments/${attachment.id}/download/`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!r.ok) throw new Error("Не удалось скачать файл");
  const url = URL.createObjectURL(await r.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = attachment.original_name;
  link.click();
  URL.revokeObjectURL(url);
}

function Login({ onLogin }: { onLogin: (p: Profile) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await fetch(`${API}/auth/login/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!r.ok) throw new Error();
      const d = await r.json();
      sessionStorage.setItem("access", d.access);
      sessionStorage.setItem("refresh", d.refresh);
      onLogin(d.user);
    } catch {
      setError("Не удалось войти. Проверьте почту и пароль.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-brand">
        <div className="logo large">
          <span>A</span> AYS Connect
        </div>
        <div>
          <p className="eyebrow">Единая рабочая среда</p>
          <h1>Всё важное для работы — в одном месте.</h1>
          <p>Задачи, объекты, команда и операционные процессы компании.</p>
        </div>
        <div className="trust">
          <ShieldCheck /> Защищённый корпоративный доступ
        </div>
      </section>
      <section className="login-panel">
        <form className="login-card" onSubmit={submit}>
          <div className="mobile-logo logo">
            <span>A</span> AYS Connect
          </div>
          <p className="eyebrow blue">Добро пожаловать</p>
          <h2>Вход в систему</h2>
          <p className="muted">Используйте корпоративную учётную запись</p>
          <label>
            Электронная почта
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              required
            />
          </label>
          <label>
            Пароль
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              required
            />
          </label>
          {error && <div className="error">{error}</div>}
          <button className="primary" disabled={busy}>
            {busy ? "Входим…" : "Войти"}
            <ChevronRight size={18} />
          </button>
          <a href="/register">Зарегистрироваться</a>
        </form>
      </section>
    </main>
  );
}

const nav = [
  ["Главная", LayoutDashboard],
  ["Задачи", CheckCircle2],
  ["Чек-листы", ClipboardCheck],
  ["Объекты", Building2],
  ["Сотрудники", Users],
  ["Уведомления", Bell],
] as const;
function initials(name: string) {
  return name
    .split(" ")
    .slice(0, 2)
    .map((x) => x[0])
    .join("");
}
function App() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobile, setMobile] = useState(false);
  const [path, setPath] = useState(window.location.pathname);
  const navigate = (next: string) => {
    window.history.pushState({}, "", next);
    setPath(next);
    setMobile(false);
    window.scrollTo(0, 0);
  };
  useEffect(() => {
    const syncPath = () => setPath(window.location.pathname);
    window.addEventListener("popstate", syncPath);
    return () => window.removeEventListener("popstate", syncPath);
  }, []);
  if (path === "/register") return <RegistrationPage />;
  if (path.startsWith("/activate/")) return <ActivationPage token={decodeURIComponent(path.slice("/activate/".length))} />;
  const [view, setView] = useState<
    | "dashboard"
    | "tasks"
    | "checklists"
    | "sensors"
    | "incidents"
    | "analytics"
    | "knowledge"
    | "learning"
    | "notifications"
    | "notification-settings"
  >(
    window.location.hash === "#tasks"
      ? "tasks"
      : window.location.hash === "#checklists"
        ? "checklists"
        : window.location.hash === "#sensors"
          ? "sensors"
          : window.location.hash === "#incidents"
            ? "incidents"
            : window.location.hash === "#analytics"
              ? "analytics"
              : window.location.hash.startsWith("#knowledge")
                ? "knowledge"
                : window.location.hash.startsWith("#learning")
                  ? "learning"
                  : window.location.hash === "#notification-settings"
                    ? "notification-settings"
                    : window.location.hash === "#notifications"
                      ? "notifications"
                      : "dashboard",
  );
  useEffect(() => {
    const syncRoute = () =>
      setView(
        window.location.hash === "#tasks"
          ? "tasks"
          : window.location.hash === "#checklists"
            ? "checklists"
            : window.location.hash === "#sensors"
              ? "sensors"
              : window.location.hash === "#incidents"
                ? "incidents"
                : window.location.hash === "#analytics"
                  ? "analytics"
                  : window.location.hash.startsWith("#knowledge")
                    ? "knowledge"
                    : window.location.hash.startsWith("#learning")
                      ? "learning"
                      : window.location.hash === "#notification-settings"
                        ? "notification-settings"
                        : window.location.hash === "#notifications"
                          ? "notifications"
                          : "dashboard",
      );
    window.addEventListener("hashchange", syncRoute);
    return () => window.removeEventListener("hashchange", syncRoute);
  }, []);
  useEffect(() => {
    const token = sessionStorage.getItem("access");
    if (!token) {
      setLoading(false);
      return;
    }
    fetch(`${API}/auth/me/`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setProfile)
      .catch(() => sessionStorage.clear())
      .finally(() => setLoading(false));
  }, []);
  if (loading) return <div className="loader">AYS</div>;
  if (!profile) return <Login onLogin={setProfile} />;
  const emp = profile.employee;
  const logout = () => {
    const refresh = sessionStorage.getItem("refresh");
    if (refresh)
      fetch(`${API}/auth/logout/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      }).catch(() => undefined);
    sessionStorage.clear();
    setProfile(null);
  };
  return (
    <div className="app-shell">
      <aside className={mobile ? "sidebar open" : "sidebar"}>
        <div className="logo">
          <span>A</span> AYS Connect
          <button className="close" onClick={() => setMobile(false)}>
            <X />
          </button>
        </div>
        <div className="company">
          <div className="company-mark">AH</div>
          <div>
            <b>AYS Hospitality</b>
            <span>Рабочее пространство</span>
          </div>
        </div>
        <nav>
          <a
            href="#dashboard"
            className={path === "/" && view === "dashboard" ? "active" : ""}
            onClick={(event) => {
              event.preventDefault();
              navigate("/");
              setView("dashboard");
            }}
          >
            <LayoutDashboard size={19} />
            Главная
          </a>
          <a
            href="/tasks"
            className={path.startsWith("/tasks") ? "active" : ""}
            onClick={(event) => {
              event.preventDefault();
              navigate("/tasks");
            }}
          >
            <CheckCircle2 size={19} />
            Задачи
          </a>
          <a
            href="/requests"
            className={path.startsWith("/requests") ? "active" : ""}
            onClick={(event) => {
              event.preventDefault();
              navigate("/requests");
            }}
          >
            <Wrench size={19} />
            Заявки
          </a>
          <a href="/people/employees" className={path.startsWith("/people") ? "active" : ""} onClick={(event) => { event.preventDefault(); navigate("/people/employees"); }}><Users size={19} />Сотрудники</a>
          <a
            href="#checklists"
            className={view === "checklists" ? "active" : ""}
            onClick={() => setMobile(false)}
          >
            <ClipboardCheck size={19} />
            Чек-листы
          </a>
          <a
            href="#sensors"
            className={view === "sensors" ? "active" : ""}
            onClick={() => setMobile(false)}
          >
            <Activity size={19} />
            Датчики
          </a>
          <a
            href="#incidents"
            className={view === "incidents" ? "active" : ""}
            onClick={() => setMobile(false)}
          >
            <Bell size={19} />
            Инциденты
          </a>
          <a
            href="#learning"
            className={view === "learning" ? "active" : ""}
            onClick={() => setMobile(false)}
          >
            <GraduationCap size={19} />
            Обучение
          </a>
          <a
            href="#knowledge"
            className={view === "knowledge" ? "active" : ""}
            onClick={() => setMobile(false)}
          >
            <BookOpen size={19} />
            Рабочие материалы
          </a>
          <a
            href="#analytics"
            className={view === "analytics" ? "active" : ""}
            onClick={() => setMobile(false)}
          >
            <Gauge size={19} />
            Эффективность
          </a>
          {nav.slice(3, 4).map(([n, I]) => (
            <button key={n}>
              <I size={19} />
              {n}
            </button>
          ))}
          <a
            href="#notifications"
            className={view === "notifications" ? "active" : ""}
            onClick={() => setMobile(false)}
          >
            <Bell size={19} />
            Уведомления<i>3</i>
          </a>
        </nav>
        <div className="sidebar-bottom">
          <small className="build-version">Work Core {APP_VERSION}</small>
          <button
            onClick={() => (window.location.hash = "#notification-settings")}
          >
            <Settings size={19} />
            Настройки
          </button>
          <button onClick={logout}>
            <LogOut size={19} />
            Выйти
          </button>
          <div className="user-mini">
            <div className="avatar">{initials(profile.full_name)}</div>
            <div>
              <b>{profile.full_name}</b>
              <span>{emp?.position}</span>
            </div>
          </div>
        </div>
      </aside>
      {mobile && <div className="scrim" onClick={() => setMobile(false)} />}
      <div className="workspace">
        <header>
          <button className="hamb" onClick={() => setMobile(true)}>
            <Menu />
          </button>
          <div className="search">
            <Search size={18} />
            <span>Поиск по AYS Connect</span>
            <kbd>⌘ K</kbd>
          </div>
          <div className="header-actions">
            <NotificationBell />
            <div className="avatar small">{initials(profile.full_name)}</div>
          </div>
        </header>
        {path.startsWith("/people") ? (
          <PeopleRouter path={path} navigate={navigate} />
        ) : path.startsWith("/tasks") || path.startsWith("/requests") ? (
          <ProductionWorkRouter path={path} navigate={navigate} />
        ) : view === "notifications" ? (
          <NotificationsView />
        ) : view === "notification-settings" ? (
          <NotificationSettingsView />
        ) : view === "learning" ? (
          <LearningView />
        ) : view === "knowledge" ? (
          <KnowledgeView />
        ) : view === "analytics" ? (
          <ProductionPerformanceView />
        ) : view === "incidents" ? (
          <IncidentsView />
        ) : view === "sensors" ? (
          <SensorsView />
        ) : view === "checklists" ? (
          <ChecklistsView />
        ) : view === "dashboard" ? (
          <WorkHome navigate={navigate} />
        ) : (
          <main className="dashboard">
            <div className="welcome">
              <div>
                <p className="eyebrow blue">Понедельник, 3 августа</p>
                <h1>
                  Добрый день,{" "}
                  {profile.full_name.split(" ")[1] || profile.full_name}!
                </h1>
                <p>Вот что требует вашего внимания сегодня.</p>
              </div>
              {profile.is_demo && (
                <span className="demo-badge">Демонстрационные данные</span>
              )}
            </div>
            <section className="stats">
              <Stat
                icon={CheckCircle2}
                color="blue"
                value="6"
                label="Задач на сегодня"
                note="2 высокого приоритета"
              />
              <Stat
                icon={ClipboardCheck}
                color="green"
                value="2"
                label="Чек-листа"
                note="Один до 12:00"
              />
              <Stat
                icon={Wrench}
                color="orange"
                value="1"
                label="Обращение"
                note="Ожидает уточнения"
              />
              <Stat
                icon={Bell}
                color="red"
                value="3"
                label="Уведомления"
                note="Одно важное"
              />
            </section>
            <div className="grid">
              <section className="card today">
                <div className="card-head">
                  <div>
                    <h2>Сегодня</h2>
                    <p>Ближайшие дела и события</p>
                  </div>
                  <button onClick={() => setView("tasks")}>
                    Все задачи <ChevronRight size={17} />
                  </button>
                </div>
                <Task
                  time="09:30"
                  title="Проверить вентиляцию в зоне кухни"
                  tag="Высокий"
                  tone="red"
                />
                <Task
                  time="11:00"
                  title="Ежедневный осмотр технических помещений"
                  tag="Чек-лист"
                  tone="blue"
                />
                <Task
                  time="14:00"
                  title="Заменить фильтр системы водоочистки"
                  tag="В работе"
                  tone="orange"
                />
                <Task
                  time="17:30"
                  title="Передать смену и заполнить журнал"
                  tag="Обычный"
                  tone="gray"
                />
              </section>
              <aside className="card profile-card">
                <div className="profile-cover">
                  <div className="avatar big">
                    {initials(profile.full_name)}
                  </div>
                </div>
                <div className="profile-body">
                  <h2>{profile.full_name}</h2>
                  <p>{emp?.position}</p>
                  <span className="status">
                    <i /> На смене
                  </span>
                  <dl>
                    <div>
                      <dt>Подразделение</dt>
                      <dd>{emp?.department}</dd>
                    </div>
                    <div>
                      <dt>Основной объект</dt>
                      <dd>Ресторан «Север»</dd>
                    </div>
                    <div>
                      <dt>График</dt>
                      <dd>2/2 · 08:00–20:00</dd>
                    </div>
                    <div>
                      <dt>Табельный номер</dt>
                      <dd>{emp?.employee_number}</dd>
                    </div>
                  </dl>
                  <button className="secondary">Открыть профиль</button>
                </div>
              </aside>
              <section className="card objects">
                <div className="card-head">
                  <div>
                    <h2>Мои объекты</h2>
                    <p>Текущее состояние зон ответственности</p>
                  </div>
                  <button>
                    Все объекты <ChevronRight size={17} />
                  </button>
                </div>
                <div className="object-row">
                  <div className="object-icon">
                    <Building2 />
                  </div>
                  <div>
                    <b>Ресторан «Север»</b>
                    <span>Демонстрационный адрес, 10</span>
                  </div>
                  <span className="ok">
                    <i /> Работает штатно
                  </span>
                  <ChevronRight />
                </div>
              </section>
              <section className="card pulse">
                <div className="card-head">
                  <div>
                    <h2>Моя эффективность</h2>
                    <p>Предварительный обзор за 30 дней</p>
                  </div>
                </div>
                <div className="score">
                  <div>
                    <Gauge />
                    <b>92</b>
                    <span>из 100</span>
                  </div>
                  <p>
                    <b>Стабильно высокий результат</b>
                    <span>Подробный расчёт появится на этапе аналитики</span>
                  </p>
                </div>
                <div className="bars">
                  <label>
                    Выполнение в срок <b>94%</b>
                  </label>
                  <div>
                    <i style={{ width: "94%" }} />
                  </div>
                  <label>
                    Качество результата <b>91%</b>
                  </label>
                  <div>
                    <i style={{ width: "91%" }} />
                  </div>
                </div>
              </section>
            </div>
          </main>
        )}
      </div>
    </div>
  );
}
function Stat({
  icon: I,
  color,
  value,
  label,
  note,
}: {
  icon: any;
  color: string;
  value: string;
  label: string;
  note: string;
}) {
  return (
    <article className="stat">
      <div className={`stat-icon ${color}`}>
        <I />
      </div>
      <div>
        <b>{value}</b>
        <span>{label}</span>
        <small>{note}</small>
      </div>
    </article>
  );
}
function Task({
  time,
  title,
  tag,
  tone,
}: {
  time: string;
  title: string;
  tag: string;
  tone: string;
}) {
  return (
    <div className="task">
      <span className="task-time">{time}</span>
      <button className="check" />
      <div>
        <b>{title}</b>
        <span>Ресторан «Север»</span>
      </div>
      <em className={tone}>{tag}</em>
      <ChevronRight size={18} />
    </div>
  );
}
function ChecklistsView() {
  const [runs, setRuns] = useState<ChecklistRunData[]>([]);
  const [run, setRun] = useState<ChecklistRunData | null>(null);
  const [answers, setAnswers] = useState<Record<number, unknown>>({});
  const [error, setError] = useState("");
  const load = () => api("/checklists/runs/").then((d) => setRuns(d.results));
  useEffect(() => {
    load();
  }, []);
  async function open(item: ChecklistRunData) {
    setRun(await api(`/checklists/runs/${item.id}/`));
    setAnswers({});
    setError("");
  }
  async function complete() {
    if (!run) return;
    try {
      const result = await api(`/checklists/runs/${run.id}/complete/`, {
        method: "POST",
        body: JSON.stringify({
          answers: run.template.questions
            .filter((q) => answers[q.id] !== undefined)
            .map((q) => ({ question: q.id, value: answers[q.id] })),
        }),
      });
      setRun(result);
      setError("");
      load();
    } catch (e) {
      setError("Заполните все обязательные пункты корректными значениями");
    }
  }
  return (
    <main className="tasks-page">
      <div className="tasks-title">
        <div>
          <p className="eyebrow blue">Контроль качества</p>
          <h1>Чек-листы</h1>
          <p>Проверки, ХАССП и корректирующие действия</p>
        </div>
      </div>
      <div className="checklist-summary">
        <Stat
          icon={ClipboardCheck}
          color="blue"
          value={String(runs.filter((x) => x.status === "assigned").length)}
          label="Назначено"
          note="Ожидают прохождения"
        />
        <Stat
          icon={ShieldCheck}
          color="green"
          value={String(runs.filter((x) => x.template.is_haccp).length)}
          label="ХАССП"
          note="Обязательные проверки"
        />
        <Stat
          icon={Bell}
          color="red"
          value={String(runs.reduce((n, x) => n + x.violations.length, 0))}
          label="Нарушения"
          note="Создают задачи"
        />
      </div>
      <section className="checklist-list">
        {runs.map((x) => (
          <button key={x.id} onClick={() => open(x)}>
            <div
              className={
                x.template.is_haccp ? "check-icon haccp" : "check-icon"
              }
            >
              <ClipboardCheck />
            </div>
            <span>
              <b>{x.template.name}</b>
              <small>
                {x.template.category} · {x.facility_name}
              </small>
            </span>
            <em className={`status-pill ${x.status}`}>{x.status_label}</em>
            <span className="check-due">
              до{" "}
              {new Date(x.due_at).toLocaleString("ru-RU", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
            <ChevronRight />
          </button>
        ))}
      </section>
      {run && (
        <div className="drawer-scrim" onClick={() => setRun(null)}>
          <aside
            className="task-drawer checklist-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <button className="drawer-close" onClick={() => setRun(null)}>
              <X />
            </button>
            <p className="eyebrow blue">
              {run.template.is_haccp ? "ХАССП" : "Проверка"}
            </p>
            <h2>{run.template.name}</h2>
            <p>{run.template.description}</p>
            <div className="check-meta">
              <span>{run.facility_name}</span>
              <em className={`status-pill ${run.status}`}>
                {run.status_label}
              </em>
            </div>
            {run.status === "assigned" || run.status === "in_progress" ? (
              <div className="question-list">
                {run.template.questions.map((q, i) => (
                  <label key={q.id}>
                    <b>
                      {i + 1}. {q.text}
                      {q.is_required && <sup>*</sup>}
                    </b>
                    {q.question_type === "boolean" ? (
                      <div className="boolean-choice">
                        <button
                          className={answers[q.id] === true ? "chosen" : ""}
                          onClick={() =>
                            setAnswers({ ...answers, [q.id]: true })
                          }
                        >
                          Да
                        </button>
                        <button
                          className={
                            answers[q.id] === false ? "chosen bad" : ""
                          }
                          onClick={() =>
                            setAnswers({ ...answers, [q.id]: false })
                          }
                        >
                          Нет
                        </button>
                      </div>
                    ) : (
                      <input
                        type={
                          ["number", "temperature", "humidity"].includes(
                            q.question_type,
                          )
                            ? "number"
                            : "text"
                        }
                        value={String(answers[q.id] ?? "")}
                        onChange={(e) =>
                          setAnswers({
                            ...answers,
                            [q.id]: [
                              "number",
                              "temperature",
                              "humidity",
                            ].includes(q.question_type)
                              ? Number(e.target.value)
                              : e.target.value,
                          })
                        }
                        placeholder={
                          q.min_value !== null
                            ? `Допустимо: ${q.min_value}–${q.max_value}`
                            : "Введите ответ"
                        }
                      />
                    )}
                  </label>
                ))}
                {error && <div className="error">{error}</div>}
                <button className="complete-check" onClick={complete}>
                  Завершить проверку
                </button>
              </div>
            ) : (
              <div className="check-result">
                <CheckCircle2 />
                <h3>Проверка завершена</h3>
                <b>{run.score}%</b>
                <p>
                  {run.violations.length
                    ? `Выявлено нарушений: ${run.violations.length}`
                    : "Нарушений не выявлено"}
                </p>
                {run.violations.map((v) => (
                  <span key={v.id}>
                    {v.description} · задача #{v.task_id}
                  </span>
                ))}
              </div>
            )}
          </aside>
        </div>
      )}
    </main>
  );
}

function SensorsView() {
  const [items, setItems] = useState<SensorData[]>([]);
  const [selected, setSelected] = useState<SensorData | null>(null);
  useEffect(() => {
    api("/sensors/").then((d) => setItems(d.results));
  }, []);
  async function open(id: number) {
    setSelected(await api(`/sensors/${id}/`));
  }
  const readings = (selected?.readings || []).slice(0, 48).reverse();
  const values = readings.map((x) => Number(x.value));
  const min = values.length ? Math.min(...values) : 0,
    max = values.length ? Math.max(...values) : 1;
  const points = values
    .map(
      (v, i) =>
        `${(i * 600) / Math.max(values.length - 1, 1)},${140 - ((v - min) * 120) / Math.max(max - min, 1)}`,
    )
    .join(" ");
  return (
    <main className="tasks-page">
      <div className="tasks-title">
        <div>
          <p className="eyebrow blue">Мониторинг объектов</p>
          <h1>Датчики</h1>
          <p>Показания, связь и техническое состояние</p>
        </div>
      </div>
      <div className="sensor-summary">
        <Stat
          icon={Activity}
          color="green"
          value={String(items.filter((x) => x.state === "normal").length)}
          label="В норме"
          note="Передают данные"
        />
        <Stat
          icon={Bell}
          color="red"
          value={String(items.filter((x) => x.state === "critical").length)}
          label="Критические"
          note="Требуют реакции"
        />
        <Stat
          icon={Gauge}
          color="orange"
          value={String(items.filter((x) => x.battery_level < 20).length)}
          label="Низкий заряд"
          note="Менее 20%"
        />
      </div>
      <section className="sensor-grid">
        {items.map((x) => (
          <button key={x.id} onClick={() => open(x.id)}>
            <span className={`sensor-label ${x.state}`}>{x.state_label}</span>
            <h3>{x.name}</h3>
            <p>
              {x.facility_name} · {x.zone_name}
            </p>
            <strong>
              {x.latest?.value || "—"} <small>{x.unit}</small>
            </strong>
            <div>
              <span>
                Батарея <b>{x.battery_level}%</b>
              </span>
              <span>
                Сигнал <b>{x.signal_quality}%</b>
              </span>
            </div>
          </button>
        ))}
      </section>
      {selected && (
        <div className="drawer-scrim" onClick={() => setSelected(null)}>
          <aside
            className="task-drawer sensor-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <button className="drawer-close" onClick={() => setSelected(null)}>
              <X />
            </button>
            <p className="eyebrow blue">{selected.serial_number}</p>
            <h2>{selected.name}</h2>
            <div className="sensor-current">
              <b>
                {selected.latest?.value} {selected.unit}
              </b>
              <em className={`sensor-label ${selected.state}`}>
                {selected.state_label}
              </em>
            </div>
            <div className="thresholds">
              <span>
                Допустимо{" "}
                <b>
                  {selected.allowed_min}…{selected.allowed_max} {selected.unit}
                </b>
              </span>
              <span>
                Критично{" "}
                <b>
                  {selected.critical_min}…{selected.critical_max}{" "}
                  {selected.unit}
                </b>
              </span>
            </div>
            <h3>График за последние 12 часов</h3>
            <div className="sensor-chart">
              <svg viewBox="0 0 600 150" preserveAspectRatio="none">
                <line x1="0" y1="140" x2="600" y2="140" />
                <polyline points={points} />
              </svg>
              <span>
                {max.toFixed(1)} {selected.unit}
              </span>
              <span>
                {min.toFixed(1)} {selected.unit}
              </span>
            </div>
            <h3>События</h3>
            <div className="sensor-events">
              {selected.events?.slice(0, 5).map((e) => (
                <div key={e.id}>
                  <i className={e.level} />
                  <span>
                    <b>
                      {e.level === "critical"
                        ? "Критическое отклонение"
                        : "Предупреждение"}
                    </b>
                    <small>
                      {new Date(e.started_at).toLocaleString("ru-RU")} · пик{" "}
                      {e.peak_value}
                    </small>
                  </span>
                </div>
              ))}
            </div>
          </aside>
        </div>
      )}
    </main>
  );
}

function IncidentsView() {
  const [items, setItems] = useState<IncidentData[]>([]);
  const [selected, setSelected] = useState<IncidentData | null>(null);
  const load = () => api("/incidents/").then((d) => setItems(d.results));
  useEffect(() => {
    load();
  }, []);
  async function open(id: number) {
    setSelected(await api(`/incidents/${id}/`));
  }
  async function act(name: string, body = {}) {
    if (!selected) return;
    const x = await api(`/incidents/${selected.id}/${name}/`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    setSelected(x);
    load();
  }
  return (
    <main className="tasks-page">
      <div className="tasks-title">
        <div>
          <p className="eyebrow blue">Центр реагирования</p>
          <h1>Инциденты</h1>
          <p>Критические события и статус устранения</p>
        </div>
      </div>
      <div className="incident-summary">
        <Stat
          icon={Bell}
          color="red"
          value={String(
            items.filter((x) => !["closed", "false_alarm"].includes(x.status))
              .length,
          )}
          label="Активные"
          note="Требуют реакции"
        />
        <Stat
          icon={CheckCircle2}
          color="green"
          value={String(items.filter((x) => x.status === "closed").length)}
          label="Закрытые"
          note="Нормализованы"
        />
        <Stat
          icon={Wrench}
          color="orange"
          value={String(items.filter((x) => x.task_id).length)}
          label="Технические задачи"
          note="Созданы из инцидентов"
        />
      </div>
      <section className="incident-list">
        {items.map((x) => (
          <button key={x.id} onClick={() => open(x.id)}>
            <i className={`incident-level ${x.level}`} />
            <span>
              <b>{x.deviation_type}</b>
              <small>
                {x.sensor_name} · {x.facility_name}
              </small>
            </span>
            <strong>
              {x.peak_value} {x.unit}
            </strong>
            <em className={`status-pill ${x.status}`}>{x.status_label}</em>
            <span>{new Date(x.started_at).toLocaleString("ru-RU")}</span>
            <ChevronRight />
          </button>
        ))}
      </section>
      {selected && (
        <div className="drawer-scrim" onClick={() => setSelected(null)}>
          <aside
            className="task-drawer incident-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <button className="drawer-close" onClick={() => setSelected(null)}>
              <X />
            </button>
            <p className="eyebrow blue">Инцидент #{selected.id}</p>
            <h2>{selected.deviation_type}</h2>
            <div className="incident-peak">
              <span>{selected.sensor_name}</span>
              <b>
                {selected.peak_value} {selected.unit}
              </b>
              <em className={`status-pill ${selected.status}`}>
                {selected.status_label}
              </em>
            </div>
            <dl>
              <div>
                <dt>Объект</dt>
                <dd>{selected.facility_name}</dd>
              </div>
              <div>
                <dt>Зона</dt>
                <dd>{selected.zone_name}</dd>
              </div>
              <div>
                <dt>Начало</dt>
                <dd>{new Date(selected.started_at).toLocaleString("ru-RU")}</dd>
              </div>
              <div>
                <dt>Время реакции</dt>
                <dd>
                  {selected.response_seconds !== null
                    ? `${selected.response_seconds} сек.`
                    : "—"}
                </dd>
              </div>
            </dl>
            <div className="drawer-actions">
              {["open", "notified"].includes(selected.status) && (
                <button onClick={() => act("acknowledge")}>
                  Принять событие
                </button>
              )}
              {["acknowledged", "in_progress"].includes(selected.status) && (
                <button
                  onClick={() =>
                    act("escalate", {
                      comment: "Требуется техническая диагностика",
                    })
                  }
                >
                  Создать техзадачу
                </button>
              )}
              {selected.status === "normalized" && (
                <button
                  onClick={() =>
                    act("close", { reason: "Показатель стабилен" })
                  }
                >
                  Закрыть инцидент
                </button>
              )}
            </div>
            {selected.response_run_id && (
              <div className="related-card">
                <ClipboardCheck />
                <span>
                  <b>Диагностический чек-лист</b>
                  <small>Назначение #{selected.response_run_id}</small>
                </span>
              </div>
            )}
            {selected.task_id && (
              <div className="related-card">
                <Wrench />
                <span>
                  <b>Техническая задача #{selected.task_id}</b>
                  <small>Создана автоматически</small>
                </span>
              </div>
            )}
            <h3>История</h3>
            <div className="timeline">
              {selected.history.map((h) => (
                <div key={h.id}>
                  <i />
                  <p>
                    <b>{h.actor_name || "Система"}</b>
                    <span>
                      {h.action} ·{" "}
                      {new Date(h.created_at).toLocaleString("ru-RU")}
                    </span>
                  </p>
                </div>
              ))}
            </div>
          </aside>
        </div>
      )}
    </main>
  );
}

function ProductionPerformanceView() {
  const [data, setData] = useState<ProductionPerformance | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const token = sessionStorage.getItem("access");
    fetch(`${INTERNAL_API}/performance/me/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Не удалось загрузить показатели");
        return response.json();
      })
      .then(setData)
      .catch((error) => setError(error.message));
  }, []);
  if (error)
    return (
      <main className="tasks-page">
        <div className="method-card">
          <ShieldCheck />
          <div>
            <h3>Показатели пока недоступны</h3>
            <p>{error}</p>
          </div>
        </div>
      </main>
    );
  if (!data)
    return (
      <main className="tasks-page">
        <div className="loader">AYS</div>
      </main>
    );
  const metric = (code: string) =>
    data.metrics[code] || {
      value: null,
      sample_size: 0,
      status: "no_data",
      explanation: {},
    };
  const format = (code: string, suffix = "") =>
    metric(code).value == null
      ? "—"
      : `${Math.round(metric(code).value!)}${suffix}`;
  const cards = [
    ["tasks_completed", "Завершено задач", ""],
    ["task_deadline_compliance", "В срок", "%"],
    ["requests_resolved", "Решено заявок", ""],
    ["sla_resolution_compliance", "SLA решения", "%"],
    ["active_tasks", "Активная нагрузка", ""],
    ["overdue_tasks", "Просрочено сейчас", ""],
  ];
  return (
    <main className="tasks-page management-page">
      <div className="tasks-title">
        <div>
          <p className="eyebrow blue">Эффективность · production analytics</p>
          <h1>{data.employee.name}</h1>
          <p>
            {data.employee.position} · период{" "}
            {new Date(data.period.from).toLocaleDateString("ru-RU")} —{" "}
            {new Date(data.period.to).toLocaleDateString("ru-RU")}
          </p>
        </div>
      </div>
      <section className="management-summary performance-summary">
        {cards.map(([code, title, suffix]) => (
          <article
            key={code}
            className={metric(code).status === "no_data" ? "muted" : ""}
          >
            <Gauge />
            <span>
              <b>{format(code, suffix)}</b>
              {title}
              <small>
                {metric(code).sample_size
                  ? `выборка: ${metric(code).sample_size}`
                  : "нет достаточных данных"}
              </small>
            </span>
          </article>
        ))}
      </section>
      <div className="management-columns">
        <section className="management-card">
          <div className="card-heading">
            <h2>Поток и сроки</h2>
            <p>Метрики событий в полуинтервале {data.period.semantics}</p>
          </div>
          <div className="metric-grid">
            <article>
              <div>
                <b>Backlog заявок</b>
                <strong>{format("backlog_requests")}</strong>
              </div>
              <p>Текущий снимок незакрытого потока</p>
            </article>
            <article>
              <div>
                <b>Переносы сроков</b>
                <strong>{format("deadline_changes")}</strong>
              </div>
              <p>Не трактуется как личная вина без контекста</p>
            </article>
          </div>
        </section>
        <section className="management-card">
          <div className="card-heading">
            <h2>Как читать показатели</h2>
            <p>Прозрачная методика без скрытого рейтинга</p>
          </div>
          <div className="method-card">
            <ShieldCheck />
            <div>
              <h3>Ожидание и переназначение учитываются отдельно</h3>
              <p>
                Время ожидания заявителя или внешней стороны не приписывается
                сотруднику как рабочая задержка. После переназначения
                ответственность считается по историческому интервалу.
              </p>
            </div>
          </div>
          <div className="method-card">
            <Clock3 />
            <div>
              <h3>Недостаточно данных — не ноль</h3>
              <p>
                Пустая выборка показывается нейтральным статусом. Версия
                расчёта: {data.calculation_version}, часовой пояс:{" "}
                {data.period.timezone}.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function AnalyticsView({ profile }: { profile: Profile }) {
  const [data, setData] = useState<PerformanceData | null>(null);
  const [management, setManagement] = useState<ManagementData | null>(null);
  const [analyticsMode, setAnalyticsMode] = useState<"personal" | "management">(
    "personal",
  );
  const canManage = profile.roles.some((r) =>
    [
      "manager",
      "facility_manager",
      "admin",
      "executive",
      "owner",
      "hr",
    ].includes(r.code),
  );
  useEffect(() => {
    api("/analytics/me/").then(setData);
    if (canManage) api("/analytics/management/").then(setManagement);
  }, []);
  if (analyticsMode === "management" && management)
    return (
      <main className="tasks-page management-page">
        <div className="tasks-title">
          <div>
            <p className="eyebrow blue">Операционный контроль · 30 дней</p>
            <h1>{management.company.name}</h1>
            <p>Сводка по объектам, команде и отклонениям</p>
          </div>
          <div className="analytics-switch">
            <button onClick={() => setAnalyticsMode("personal")}>
              Мои показатели
            </button>
            <button className="active">Компания</button>
          </div>
        </div>
        <section className="management-summary">
          <article>
            <Users />
            <span>
              <b>{management.summary.employee_count}</b>Сотрудников
            </span>
          </article>
          <article>
            <Gauge />
            <span>
              <b>{management.summary.average_score}</b>Средняя оценка
            </span>
          </article>
          <article>
            <ClipboardCheck />
            <span>
              <b>{management.summary.active_tasks}</b>Активных задач
            </span>
          </article>
          <article
            className={management.summary.overdue_tasks ? "warning" : ""}
          >
            <CalendarDays />
            <span>
              <b>{management.summary.overdue_tasks}</b>Просрочено
            </span>
          </article>
          <article
            className={management.summary.open_incidents ? "danger" : ""}
          >
            <Bell />
            <span>
              <b>{management.summary.open_incidents}</b>Инцидентов
            </span>
          </article>
        </section>
        <div className="management-columns">
          <section className="management-card">
            <div className="card-heading">
              <div>
                <h2>Состояние объектов</h2>
                <p>Нагрузка, инциденты и качество проверок</p>
              </div>
            </div>
            <div className="facility-health">
              {management.facilities.map((f) => {
                const risk = f.open_incidents > 0 || f.checklist_score < 85;
                return (
                  <article key={f.id}>
                    <span className={`health-dot ${risk ? "risk" : "ok"}`} />
                    <div>
                      <b>{f.name}</b>
                      <small>
                        {risk ? "Требует внимания" : "Работает штатно"}
                      </small>
                    </div>
                    <dl>
                      <div>
                        <dt>Задачи</dt>
                        <dd>{f.active_tasks}</dd>
                      </div>
                      <div>
                        <dt>Инциденты</dt>
                        <dd>{f.open_incidents}</dd>
                      </div>
                      <div>
                        <dt>Чек-листы</dt>
                        <dd>{f.checklist_score}%</dd>
                      </div>
                    </dl>
                  </article>
                );
              })}
            </div>
          </section>
          <section className="management-card">
            <div className="card-heading">
              <div>
                <h2>Команда</h2>
                <p>Рейтинг по объективным показателям</p>
              </div>
            </div>
            <div className="team-ranking">
              {management.employees.map((e, index) => (
                <article key={e.employee_id}>
                  <em>{index + 1}</em>
                  <div>
                    <b>{e.full_name}</b>
                    <small>
                      {e.position} · {e.department}
                    </small>
                  </div>
                  <span
                    className={
                      e.score >= 85 ? "good" : e.score < 70 ? "low" : ""
                    }
                  >
                    {e.score}
                  </span>
                  <div className="mini-progress">
                    <i style={{ width: `${e.score}%` }} />
                  </div>
                  <small>
                    {e.overdue_tasks} проср. · {e.active_tasks} актив.
                  </small>
                </article>
              ))}
            </div>
          </section>
        </div>
      </main>
    );
  if (!data)
    return (
      <main className="tasks-page">
        <div className="tasks-loading">Рассчитываем показатели…</div>
      </main>
    );
  const metrics = [
    ["Выполнение в срок", data.timeliness, "Доля принятых задач без просрочки"],
    ["Качество результата", data.quality, "Учитывает возвраты на доработку"],
    ["Проверки и ХАССП", data.checklist_score, "Средний результат чек-листов"],
    [
      "Реакция на события",
      data.response_score,
      data.avg_response_seconds
        ? `Среднее время: ${data.avg_response_seconds} сек.`
        : "Инцидентов за период нет",
    ],
  ];
  return (
    <main className="tasks-page">
      <div className="tasks-title">
        <div>
          <p className="eyebrow blue">Объективные показатели · 30 дней</p>
          <h1>Моя эффективность</h1>
          <p>Результат рассчитывается по зафиксированным действиям в системе</p>
        </div>
        {canManage && (
          <div className="analytics-switch">
            <button className="active">Мои показатели</button>
            <button onClick={() => setAnalyticsMode("management")}>
              Компания
            </button>
          </div>
        )}
      </div>
      <section className="performance-hero">
        <div
          className="performance-ring"
          style={{ "--score": `${data.score * 3.6}deg` } as React.CSSProperties}
        >
          <span>
            <b>{data.score}</b>
            <small>из 100</small>
          </span>
        </div>
        <div>
          <h2>{data.full_name}</h2>
          <p>
            {data.position} · {data.department}
          </p>
          <em className={data.score >= 85 ? "excellent" : "normal"}>
            {data.score >= 85 ? "Высокий результат" : "Стабильный результат"}
          </em>
        </div>
        <div className="performance-numbers">
          <span>
            <b>{data.completed_tasks}</b>Завершено
          </span>
          <span>
            <b>{data.active_tasks}</b>Активно
          </span>
          <span>
            <b>{data.overdue_tasks}</b>Просрочено
          </span>
          <span>
            <b>{data.returned_tasks}</b>Возвратов
          </span>
        </div>
      </section>
      <section className="metric-grid">
        {metrics.map(([name, value, note]) => (
          <article key={String(name)}>
            <div>
              <b>{String(name)}</b>
              <strong>{value}%</strong>
            </div>
            <div className="metric-bar">
              <i style={{ width: `${value}%` }} />
            </div>
            <p>{String(note)}</p>
          </article>
        ))}
      </section>
      <section className="method-card">
        <ShieldCheck />
        <div>
          <h3>Как рассчитывается результат</h3>
          <p>
            40% — соблюдение сроков, 25% — качество приёмки, 20% — результаты
            проверок, 15% — скорость реакции. Согласованные зависимости и
            внешние блокировки не должны снижать оценку.
          </p>
        </div>
      </section>
    </main>
  );
}

function NotificationsView() {
  const [items, setItems] = useState<NotificationData[]>([]);
  const load = () => api("/notifications/").then((d) => setItems(d.results));
  useEffect(() => {
    load();
  }, []);
  async function mark(id: number) {
    await api(`/notifications/${id}/read/`, { method: "POST" });
    load();
  }
  async function all() {
    await api("/notifications/read-all/", { method: "POST" });
    load();
  }
  return (
    <main className="tasks-page">
      <div className="tasks-title">
        <div>
          <p className="eyebrow blue">Центр событий</p>
          <h1>Уведомления</h1>
          <p>Задачи, проверки, датчики и системные сообщения</p>
        </div>
        <button className="new-task" onClick={all}>
          Прочитать все
        </button>
      </div>
      <div className="notification-tabs">
        <span>
          Все <b>{items.length}</b>
        </span>
        <span>
          Непрочитанные <b>{items.filter((x) => !x.is_read).length}</b>
        </span>
      </div>
      <section className="notification-list">
        {items.map((x) => (
          <button
            key={x.id}
            className={x.is_read ? "read" : ""}
            onClick={() => mark(x.id)}
          >
            <div className={`notification-icon ${x.priority}`}>
              {x.priority === "critical" ? (
                <Bell />
              ) : x.entity_type === "Task" ? (
                <CheckCircle2 />
              ) : (
                <Activity />
              )}
            </div>
            <span>
              <b>{x.title}</b>
              <p>{x.message}</p>
              <small>
                {x.type_label} ·{" "}
                {new Date(x.created_at).toLocaleString("ru-RU")}
              </small>
            </span>
            {!x.is_read && <i />}
            <em />
          </button>
        ))}
      </section>
    </main>
  );
}

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationData[]>([]);
  const load = () =>
    api("/notifications/?unread=true")
      .then((d) => setItems(d.results || []))
      .catch(() => undefined);
  useEffect(() => {
    load();
    const timer = window.setInterval(load, 45000);
    return () => window.clearInterval(timer);
  }, []);
  async function select(item: NotificationData) {
    await api(`/notifications/${item.id}/read/`, { method: "POST" });
    setOpen(false);
    await load();
    if (item.action_url) window.location.href = item.action_url;
  }
  return (
    <div className="notification-bell">
      <button aria-label="Уведомления" onClick={() => setOpen(!open)}>
        <Bell />
        {items.length > 0 && <b>{items.length > 99 ? "99+" : items.length}</b>}
      </button>
      {open && (
        <div className="notification-popover">
          <strong>Непрочитанные</strong>
          {items.slice(0, 5).map((item) => (
            <button key={item.id} onClick={() => select(item)}>
              <span>{item.title}</span>
              <small>{item.message}</small>
            </button>
          ))}
          {!items.length && <p>Новых уведомлений нет</p>}
          <a href="#notifications" onClick={() => setOpen(false)}>
            Все уведомления
          </a>
        </div>
      )}
    </div>
  );
}

async function internalApi(path: string, options: RequestInit = {}) {
  const token = sessionStorage.getItem("access");
  const response = await fetch(`${INTERNAL_API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (!response.ok) throw new Error("API error");
  return response.status === 204 ? null : response.json();
}
function NotificationSettingsView() {
  const [status, setStatus] = useState<ChannelStatus | null>(null);
  const [quiet, setQuiet] = useState({
    enabled: false,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    starts_at: "22:00",
    ends_at: "08:00",
  });
  const [link, setLink] = useState("");
  const load = () =>
    Promise.all([
      internalApi("/notification-channels/"),
      internalApi("/notification-channels/quiet-hours/"),
    ]).then(([s, q]) => {
      setStatus(s);
      setQuiet(q);
    });
  useEffect(() => {
    load().catch(() => undefined);
  }, []);
  async function connect() {
    const result = await internalApi("/notification-channels/telegram/link/", {
      method: "POST",
    });
    setLink(result.deep_link);
  }
  async function unlink() {
    await internalApi("/notification-channels/telegram/unlink/", {
      method: "POST",
    });
    await load();
  }
  async function saveQuiet() {
    await internalApi("/notification-channels/quiet-hours/", {
      method: "PUT",
      body: JSON.stringify(quiet),
    });
    await load();
  }
  async function preference(channel: string, enabled: boolean) {
    await internalApi("/notification-channels/preferences/", {
      method: "PUT",
      body: JSON.stringify({ reason: "*", channel, enabled }),
    });
  }
  return (
    <main className="tasks-page notification-settings-page">
      <div className="tasks-title">
        <div>
          <p className="eyebrow blue">Каналы связи</p>
          <h1>Настройки уведомлений</h1>
          <p>
            Telegram, email и время, когда внешние сообщения следует отложить.
          </p>
        </div>
      </div>
      <section className="notification-settings-card">
        <h2>Telegram</h2>
        <p>
          {status?.telegram.linked
            ? `Подключён${status.telegram.username ? ` · @${status.telegram.username}` : ""}`
            : "Не подключён"}
        </p>
        {status?.telegram.linked ? (
          <button onClick={unlink}>Отключить</button>
        ) : (
          <button className="new-task" onClick={connect}>
            Подключить Telegram
          </button>
        )}
        {link && (
          <a href={link} target="_blank" rel="noreferrer">
            Открыть Telegram
          </a>
        )}
      </section>
      <section className="notification-settings-card">
        <h2>Каналы</h2>
        <label>
          <input type="checkbox" defaultChecked disabled /> In-App —
          обязательный для критических событий
        </label>
        <label>
          <input
            type="checkbox"
            defaultChecked
            onChange={(e) => preference("telegram", e.target.checked)}
          />{" "}
          Telegram
        </label>
        <label>
          <input
            type="checkbox"
            defaultChecked
            onChange={(e) => preference("email", e.target.checked)}
          />{" "}
          Email{" "}
          {status?.email.address_masked && `· ${status.email.address_masked}`}
        </label>
      </section>
      <section className="notification-settings-card">
        <h2>Не беспокоить</h2>
        <label>
          <input
            type="checkbox"
            checked={quiet.enabled}
            onChange={(e) => setQuiet({ ...quiet, enabled: e.target.checked })}
          />{" "}
          Включено
        </label>
        <div>
          <input
            type="time"
            value={quiet.starts_at}
            onChange={(e) => setQuiet({ ...quiet, starts_at: e.target.value })}
          />
          <span>—</span>
          <input
            type="time"
            value={quiet.ends_at}
            onChange={(e) => setQuiet({ ...quiet, ends_at: e.target.value })}
          />
        </div>
        <input
          value={quiet.timezone}
          onChange={(e) => setQuiet({ ...quiet, timezone: e.target.value })}
        />
        <button className="new-task" onClick={saveQuiet}>
          Сохранить
        </button>
      </section>
    </main>
  );
}

function LiveDashboard({
  profile,
  data,
  onTasks,
}: {
  profile: Profile;
  data: DashboardData;
  onTasks: () => void;
}) {
  const emp = profile.employee;
  const dateText = new Intl.DateTimeFormat("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());
  return (
    <main className="dashboard">
      <div className="welcome">
        <div>
          <p className="eyebrow blue">{dateText}</p>
          <h1>
            Добрый день, {profile.full_name.split(" ")[1] || profile.full_name}!
          </h1>
          <p>Вот что требует вашего внимания сегодня.</p>
        </div>
        {profile.is_demo && (
          <span className="demo-badge">Демонстрационные данные</span>
        )}
      </div>
      <section className="stats">
        <Stat
          icon={CheckCircle2}
          color="blue"
          value={String(data.counts.today)}
          label="Задач на сегодня"
          note={`${data.counts.high_priority} высокого приоритета`}
        />
        <Stat
          icon={Activity}
          color="green"
          value={String(data.counts.active)}
          label="Активные задачи"
          note="Включая совместные"
        />
        <Stat
          icon={CalendarDays}
          color="orange"
          value={String(data.counts.on_review)}
          label="На проверке"
          note="Ожидают решения"
        />
        <Stat
          icon={Bell}
          color="red"
          value={String(data.counts.overdue)}
          label="Просрочено"
          note="Требует внимания"
        />
      </section>
      <div className="grid">
        <section className="card today">
          <div className="card-head">
            <div>
              <h2>Ближайшие задачи</h2>
              <p>Рассчитано по текущим срокам</p>
            </div>
            <button onClick={onTasks}>
              Все задачи <ChevronRight size={17} />
            </button>
          </div>
          {data.today_tasks.length ? (
            data.today_tasks.slice(0, 5).map((t) => (
              <Task
                key={t.id}
                time={new Date(t.deadline).toLocaleTimeString("ru-RU", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
                title={t.title}
                tag={t.status_label}
                tone={
                  t.is_overdue
                    ? "red"
                    : t.status === "in_progress"
                      ? "orange"
                      : "blue"
                }
              />
            ))
          ) : (
            <div className="empty-dashboard">Ближайших задач нет</div>
          )}
        </section>
        <aside className="card profile-card">
          <div className="profile-cover">
            <div className="avatar big">{initials(profile.full_name)}</div>
          </div>
          <div className="profile-body">
            <h2>{profile.full_name}</h2>
            <p>{emp?.position}</p>
            <span className="status">
              <i /> На смене
            </span>
            <dl>
              <div>
                <dt>Подразделение</dt>
                <dd>{emp?.department}</dd>
              </div>
              <div>
                <dt>Основной объект</dt>
                <dd>{data.facilities[0]?.name || "Не назначен"}</dd>
              </div>
              <div>
                <dt>Табельный номер</dt>
                <dd>{emp?.employee_number}</dd>
              </div>
            </dl>
            <button className="secondary">Открыть профиль</button>
          </div>
        </aside>
        <section className="card objects">
          <div className="card-head">
            <div>
              <h2>Мои объекты</h2>
              <p>Объекты ответственности из профиля</p>
            </div>
          </div>
          {data.facilities.map((f) => (
            <div className="object-row" key={f.id}>
              <div className="object-icon">
                <Building2 />
              </div>
              <div>
                <b>{f.name}</b>
                <span>{f.address}</span>
              </div>
              <span className="ok">
                <i /> Работает штатно
              </span>
              <ChevronRight />
            </div>
          ))}
        </section>
        <section className="card pulse">
          <div className="card-head">
            <div>
              <h2>Структура загрузки</h2>
              <p>Активные задачи по статусам</p>
            </div>
          </div>
          <div className="load-statuses">
            {data.by_status.map((x) => (
              <div key={x.status}>
                <span>{x.label}</span>
                <b>{x.count}</b>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

function TasksView({ profile }: { profile: Profile }) {
  const [items, setItems] = useState<TaskData[]>([]);
  const [selected, setSelected] = useState<TaskData | null>(null);
  const [mode, setMode] = useState<"list" | "board">("list");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [scope, setScope] = useState<"my" | "created" | "review">("my");
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({
    title: "",
    description: "",
    priority: "normal",
    deadline: "",
    acceptance_criteria: "",
  });
  const [comment, setComment] = useState("");
  const [resultText, setResultText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [scheduleForm, setScheduleForm] = useState({
    frequency: "daily",
    interval: 1,
    next_run_at: "",
  });
  const [formError, setFormError] = useState("");
  const load = () => {
    setLoading(true);
    api(
      `/tasks/?scope=${scope}${statusFilter ? `&status=${statusFilter}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
    )
      .then((d) => setItems(d.results))
      .finally(() => setLoading(false));
  };
  useEffect(load, [statusFilter, scope]);
  async function open(id: number) {
    setSelected(await api(`/tasks/${id}/`));
  }
  async function act(name: string, body: object = {}) {
    if (!selected) return;
    const updated = await api(`/tasks/${selected.id}/${name}/`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    setSelected(updated);
    load();
  }
  async function createTask(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    try {
      await api("/tasks/", {
        method: "POST",
        body: JSON.stringify({
          ...createForm,
          assignee: profile.id,
          status: "assigned",
          requires_review: true,
          requires_comment: true,
        }),
      });
      setCreating(false);
      setCreateForm({
        title: "",
        description: "",
        priority: "normal",
        deadline: "",
        acceptance_criteria: "",
      });
      setScope("created");
      load();
    } catch {
      setFormError("Проверьте обязательные поля и срок задачи");
    }
  }
  async function addComment(e: React.FormEvent) {
    e.preventDefault();
    if (!comment.trim() || !selected) return;
    await api(`/tasks/${selected.id}/comment/`, {
      method: "POST",
      body: JSON.stringify({ text: comment }),
    });
    setComment("");
    await open(selected.id);
    load();
  }
  async function addAttachment(file?: File) {
    if (!file || !selected) return;
    setUploading(true);
    try {
      await upload(`/tasks/${selected.id}/attachment/`, file);
      await open(selected.id);
    } finally {
      setUploading(false);
    }
  }
  async function submitResult(e: React.FormEvent) {
    e.preventDefault();
    if (!resultText.trim()) return;
    await act("submit", { result_text: resultText });
    setResultText("");
  }
  async function saveSchedule(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || !scheduleForm.next_run_at) return;
    await api(`/tasks/${selected.id}/recurrence/`, {
      method: "POST",
      body: JSON.stringify(scheduleForm),
    });
    await open(selected.id);
  }
  const groups = [
    ["assigned", "Назначены"],
    ["accepted", "Приняты"],
    ["in_progress", "В работе"],
    ["waiting", "Ожидают"],
    ["review", "На проверке"],
    ["closed", "Закрыты"],
  ];
  return (
    <main className="tasks-page">
      <div className="tasks-title">
        <div>
          <p className="eyebrow blue">Рабочее пространство</p>
          <h1>Задачи</h1>
          <p>Планируйте работу и контролируйте результат</p>
        </div>
        <button className="new-task" onClick={() => setCreating(true)}>
          + Новая задача
        </button>
      </div>
      <div className="task-tabs">
        <button
          className={scope === "my" ? "active" : ""}
          onClick={() => setScope("my")}
        >
          Мои задачи <b>{items.length}</b>
        </button>
        <button
          className={scope === "created" ? "active" : ""}
          onClick={() => setScope("created")}
        >
          Созданные мной
        </button>
        <button
          className={scope === "review" ? "active" : ""}
          onClick={() => setScope("review")}
        >
          На проверке
        </button>
      </div>
      <div className="task-toolbar">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            load();
          }}
        >
          <Search size={17} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Найти задачу"
          />
        </form>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">Все статусы</option>
          {groups.map((g) => (
            <option value={g[0]} key={g[0]}>
              {g[1]}
            </option>
          ))}
        </select>
        <div className="view-switch">
          <button
            onClick={() => setMode("list")}
            className={mode === "list" ? "active" : ""}
          >
            Список
          </button>
          <button
            onClick={() => setMode("board")}
            className={mode === "board" ? "active" : ""}
          >
            Канбан
          </button>
        </div>
      </div>
      {loading ? (
        <div className="tasks-loading">Загружаем задачи…</div>
      ) : mode === "list" ? (
        <section className="task-table">
          <div className="task-table-head">
            <span>Задача</span>
            <span>Статус</span>
            <span>Приоритет</span>
            <span>Срок</span>
            <span>Объект</span>
          </div>
          {items.map((t) => (
            <button className="task-row" key={t.id} onClick={() => open(t.id)}>
              <span>
                <i className={`priority-dot ${t.priority}`} />
                <span>
                  <b>{t.title}</b>
                  <small>{t.category}</small>
                </span>
              </span>
              <em className={`status-pill ${t.status}`}>{t.status_label}</em>
              <span>{t.priority_label}</span>
              <span className={t.is_overdue ? "overdue" : ""}>
                {new Date(t.deadline).toLocaleString("ru-RU", {
                  day: "2-digit",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              <span>{t.facility_name || "—"}</span>
            </button>
          ))}
        </section>
      ) : (
        <section className="kanban">
          {groups.slice(0, 5).map(([code, label]) => (
            <div className="kanban-col" key={code}>
              <h3>
                {label}
                <b>{items.filter((x) => x.status === code).length}</b>
              </h3>
              {items
                .filter((x) => x.status === code)
                .map((t) => (
                  <button key={t.id} onClick={() => open(t.id)}>
                    <i className={`priority-dot ${t.priority}`} />
                    <strong>{t.title}</strong>
                    <small>{t.facility_name}</small>
                    <span>
                      <CalendarDays size={13} />
                      {new Date(t.deadline).toLocaleDateString("ru-RU")}
                    </span>
                  </button>
                ))}
            </div>
          ))}
        </section>
      )}
      {creating && (
        <div className="drawer-scrim" onClick={() => setCreating(false)}>
          <aside
            className="task-drawer create-task-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <button className="drawer-close" onClick={() => setCreating(false)}>
              <X />
            </button>
            <p className="eyebrow blue">Новая задача</p>
            <h2>Поставить задачу</h2>
            <form className="task-form" onSubmit={createTask}>
              <label>
                Название
                <input
                  required
                  value={createForm.title}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, title: e.target.value })
                  }
                />
              </label>
              <label>
                Описание
                <textarea
                  value={createForm.description}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      description: e.target.value,
                    })
                  }
                />
              </label>
              <div className="form-row">
                <label>
                  Приоритет
                  <select
                    value={createForm.priority}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, priority: e.target.value })
                    }
                  >
                    <option value="low">Низкий</option>
                    <option value="normal">Обычный</option>
                    <option value="high">Высокий</option>
                    <option value="critical">Критический</option>
                  </select>
                </label>
                <label>
                  Срок
                  <input
                    required
                    type="datetime-local"
                    value={createForm.deadline}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, deadline: e.target.value })
                    }
                  />
                </label>
              </div>
              <label>
                Критерии приёмки
                <textarea
                  value={createForm.acceptance_criteria}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      acceptance_criteria: e.target.value,
                    })
                  }
                />
              </label>
              <div className="self-assignee">
                <Users size={18} />
                <span>
                  <b>Исполнитель: {profile.full_name}</b>
                  <small>В демо-режиме задача назначается себе</small>
                </span>
              </div>
              {formError && <div className="error">{formError}</div>}
              <button className="primary">Создать задачу</button>
            </form>
          </aside>
        </div>
      )}
      {selected && (
        <div className="drawer-scrim" onClick={() => setSelected(null)}>
          <aside className="task-drawer" onClick={(e) => e.stopPropagation()}>
            <button className="drawer-close" onClick={() => setSelected(null)}>
              <X />
            </button>
            <p className="eyebrow blue">Задача #{selected.id}</p>
            <h2>{selected.title}</h2>
            <div className="drawer-badges">
              <em className={`status-pill ${selected.status}`}>
                {selected.status_label}
              </em>
              <em className={`priority-tag ${selected.priority}`}>
                {selected.priority_label}
              </em>
            </div>
            <dl>
              <div>
                <dt>Постановщик</dt>
                <dd>{selected.creator.full_name}</dd>
              </div>
              <div>
                <dt>Исполнитель</dt>
                <dd>{selected.assignee.full_name}</dd>
              </div>
              <div>
                <dt>Срок</dt>
                <dd>{new Date(selected.deadline).toLocaleString("ru-RU")}</dd>
              </div>
              <div>
                <dt>Объект</dt>
                <dd>{selected.facility_name}</dd>
              </div>
            </dl>
            <h3>Описание</h3>
            <p>{selected.description || "Описание не добавлено"}</p>
            <h3>Критерии приёмки</h3>
            <p>{selected.acceptance_criteria || "Не указаны"}</p>
            <div className="drawer-actions">
              {selected.status === "assigned" && (
                <button onClick={() => act("accept")}>Принять задачу</button>
              )}
              {["assigned", "accepted", "returned"].includes(
                selected.status,
              ) && <button onClick={() => act("start")}>Начать работу</button>}
              {selected.status === "review" &&
                selected.creator.id === profile.id && (
                  <button onClick={() => act("approve")}>
                    Принять результат
                  </button>
                )}
              {selected.status === "review" &&
                selected.creator.id === profile.id && (
                  <button
                    className="danger-action"
                    onClick={() => {
                      const reason = prompt("Причина возврата");
                      const fixes = prompt("Что исправить?");
                      const deadline = prompt(
                        "Новый срок в формате 2026-08-10T18:00:00+07:00",
                      );
                      if (reason && fixes && deadline)
                        act("return_task", {
                          reason,
                          required_fixes: fixes,
                          new_deadline: deadline,
                        });
                    }}
                  >
                    Вернуть на доработку
                  </button>
                )}
              {!["closed", "completed", "cancelled", "review"].includes(
                selected.status,
              ) && (
                <button
                  className="secondary-action"
                  onClick={() => {
                    const proposed = prompt(
                      "Предлагаемый новый срок в формате 2026-08-10T18:00:00+07:00",
                    );
                    const reason = prompt("Причина переноса");
                    if (proposed && reason)
                      act("deadline-request", {
                        proposed_deadline: proposed,
                        reason_type: "technical",
                        reason,
                      });
                  }}
                >
                  Запросить перенос
                </button>
              )}
            </div>
            {selected.status === "in_progress" && (
              <form className="result-form" onSubmit={submitResult}>
                <label>
                  Результат работы
                  <textarea
                    required
                    value={resultText}
                    onChange={(e) => setResultText(e.target.value)}
                    placeholder="Что сделано и как проверен результат"
                  />
                </label>
                <button>Отправить на проверку</button>
              </form>
            )}
            <h3>Комментарии</h3>
            <div className="task-comments">
              {selected.comments?.map((c) => (
                <div key={c.id}>
                  <b>{c.author.full_name}</b>
                  <p>{c.text}</p>
                  <small>
                    {new Date(c.created_at).toLocaleString("ru-RU")}
                  </small>
                </div>
              ))}
            </div>
            <form className="comment-form" onSubmit={addComment}>
              <input
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Добавить комментарий"
              />
              <button>Отправить</button>
            </form>
            <div className="attachments-title">
              <h3>Вложения</h3>
              <label className="attachment-upload">
                <Paperclip size={14} />
                {uploading ? "Загрузка…" : "Прикрепить файл"}
                <input
                  type="file"
                  disabled={uploading}
                  onChange={(e) => addAttachment(e.target.files?.[0])}
                />
              </label>
            </div>
            <div className="task-attachments">
              {selected.attachments?.length ? (
                selected.attachments.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => downloadAttachment(selected.id, a)}
                  >
                    <Paperclip size={15} />
                    <span>
                      <b>{a.original_name}</b>
                      <small>
                        {(a.size / 1024).toFixed(1)} КБ · {a.uploader.full_name}
                      </small>
                    </span>
                    <Download size={14} />
                  </button>
                ))
              ) : (
                <p>Файлов пока нет</p>
              )}
            </div>
            {selected.creator.id === profile.id && (
              <form className="recurrence-form" onSubmit={saveSchedule}>
                <h3>Повторение</h3>
                {selected.recurrence && (
                  <p>
                    Следующий запуск:{" "}
                    {new Date(selected.recurrence.next_run_at).toLocaleString(
                      "ru-RU",
                    )}
                  </p>
                )}
                <div>
                  <select
                    value={scheduleForm.frequency}
                    onChange={(e) =>
                      setScheduleForm({
                        ...scheduleForm,
                        frequency: e.target.value,
                      })
                    }
                  >
                    <option value="daily">Ежедневно</option>
                    <option value="weekly">Еженедельно</option>
                    <option value="monthly">Ежемесячно</option>
                  </select>
                  <input
                    aria-label="Интервал"
                    type="number"
                    min="1"
                    max="365"
                    value={scheduleForm.interval}
                    onChange={(e) =>
                      setScheduleForm({
                        ...scheduleForm,
                        interval: Number(e.target.value),
                      })
                    }
                  />
                  <input
                    aria-label="Первый запуск"
                    required
                    type="datetime-local"
                    value={scheduleForm.next_run_at}
                    onChange={(e) =>
                      setScheduleForm({
                        ...scheduleForm,
                        next_run_at: e.target.value,
                      })
                    }
                  />
                  <button>Сохранить</button>
                </div>
              </form>
            )}
            <h3>Активность</h3>
            <div className="timeline">
              {selected.history?.map((h) => (
                <div key={h.id}>
                  <i />
                  <p>
                    <b>{h.actor.full_name}</b>
                    <span>
                      {h.action} ·{" "}
                      {new Date(h.created_at).toLocaleString("ru-RU")}
                    </span>
                  </p>
                </div>
              ))}
            </div>
          </aside>
        </div>
      )}
    </main>
  );
}
function LearningView() {
  const [tabMode, setTabMode] = useState<
    "my" | "catalog" | "results" | "certificates"
  >("my");
  const [courses, setCourses] = useState<CourseData[]>([]);
  const [assignments, setAssignments] = useState<AssignmentData[]>([]);
  const [attempts, setAttempts] = useState<AttemptData[]>([]);
  const [certificates, setCertificates] = useState<CertificateData[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<CourseData | null>(null);
  const [selectedAssignment, setSelectedAssignment] =
    useState<AssignmentData | null>(null);
  const [lesson, setLesson] = useState<LessonData | null>(null);
  const [assessment, setAssessment] = useState<AssessmentData | null>(null);
  const [attempt, setAttempt] = useState<AttemptData | null>(null);
  const [answers, setAnswers] = useState<
    Record<
      number,
      {
        selected_options?: number[];
        text_answer?: string;
        number_answer?: number;
      }
    >
  >({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  async function loadLearning() {
    setLoading(true);
    setError("");
    try {
      const [c, a, r, cert] = await Promise.all([
        api("/learning/courses/"),
        api("/learning/assignments/my/"),
        api("/learning/attempts/my/"),
        api("/learning/certificates/my/"),
      ]);
      setCourses(c.results || c);
      setAssignments(a);
      setAttempts(r);
      setCertificates(cert);
    } catch {
      setError("Не удалось загрузить обучение");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void loadLearning();
  }, []);
  async function openAssignment(item: AssignmentData) {
    try {
      const [course, assessments] = await Promise.all([
        api(`/learning/courses/${item.course}/`),
        api(`/learning/assessments/?course=${item.course}`),
      ]);
      setSelectedAssignment(item);
      setSelectedCourse(course);
      const list = assessments.results || assessments;
      setAssessment(list[0] || null);
    } catch {
      setError("Курс недоступен");
    }
  }
  async function startCourse() {
    if (!selectedAssignment) return;
    try {
      const updated = await api(
        `/learning/assignments/${selectedAssignment.id}/start/`,
        { method: "POST" },
      );
      setSelectedAssignment(updated);
      setAssignments((x) => x.map((a) => (a.id === updated.id ? updated : a)));
      const all = selectedCourse?.modules?.flatMap((m) => m.lessons) || [];
      setLesson(
        all.find((x) => x.id === updated.current_lesson) || all[0] || null,
      );
    } catch {
      setError("Не удалось начать курс");
    }
  }
  async function finishLesson() {
    if (!lesson || !selectedAssignment) return;
    try {
      const result = await api(`/learning/lessons/${lesson.id}/complete/`, {
        method: "POST",
        body: JSON.stringify({
          assignment: selectedAssignment.id,
          confirmed: lesson.requires_confirmation,
          time_spent_seconds: 60,
        }),
      });
      const updated = result.assignment;
      setSelectedAssignment(updated);
      setAssignments((x) => x.map((a) => (a.id === updated.id ? updated : a)));
      const all = selectedCourse?.modules?.flatMap((m) => m.lessons) || [];
      setLesson(all.find((x) => x.id === updated.current_lesson) || null);
    } catch {
      setError("Не удалось завершить урок");
    }
  }
  async function beginTest() {
    if (!assessment || !selectedAssignment) return;
    try {
      const data = await api(`/learning/assessments/${assessment.id}/start/`, {
        method: "POST",
        body: JSON.stringify({ assignment: selectedAssignment.id }),
      });
      setAttempt(data);
      setAnswers({});
    } catch {
      setError("Тест пока недоступен или попытки исчерпаны");
    }
  }
  async function submitTest() {
    if (!attempt) return;
    try {
      const payload = attempt.questions.map((q) => ({
        question: q.id,
        ...answers[q.id],
      }));
      const result = await api(`/learning/attempts/${attempt.id}/submit/`, {
        method: "POST",
        body: JSON.stringify({ answers: payload }),
      });
      setAttempt(result);
      setAttempts((x) => [result, ...x.filter((a) => a.id !== result.id)]);
      await loadLearning();
    } catch {
      setError("Ответьте на все обязательные вопросы");
    }
  }
  const completedLessons = new Set(
    selectedAssignment?.lesson_progress
      .filter((x) => x.completed_at)
      .map((x) => x.lesson) || [],
  );
  if (attempt && attempt.status === "IN_PROGRESS")
    return (
      <main className="learning-page">
        <button className="knowledge-back" onClick={() => setAttempt(null)}>
          <ArrowLeft size={18} /> Вернуться к курсу
        </button>
        <section className="test-shell">
          <div className="test-head">
            <div>
              <p className="eyebrow blue">Попытка {attempt.attempt_number}</p>
              <h1>{attempt.assessment_title}</h1>
            </div>
            <span>
              <Clock3 size={17} />
              {assessment?.time_limit_minutes || 0} мин
            </span>
          </div>
          {attempt.questions.map((q, index) => (
            <article className="question-card" key={q.id}>
              <b>
                Вопрос {index + 1} из {attempt.questions.length}
              </b>
              <h2>{q.text}</h2>
              {q.question_type === "TEXT" ||
              q.question_type === "CASE_STUDY" ? (
                <textarea
                  value={answers[q.id]?.text_answer || ""}
                  onChange={(e) =>
                    setAnswers({
                      ...answers,
                      [q.id]: { text_answer: e.target.value },
                    })
                  }
                  placeholder="Введите ответ"
                />
              ) : q.question_type === "NUMBER" ? (
                <input
                  type="number"
                  value={answers[q.id]?.number_answer ?? ""}
                  onChange={(e) =>
                    setAnswers({
                      ...answers,
                      [q.id]: { number_answer: Number(e.target.value) },
                    })
                  }
                />
              ) : (
                <div className="answer-list">
                  {q.options.map((o) => (
                    <label key={o.id}>
                      <input
                        type={
                          q.question_type === "MULTIPLE_CHOICE"
                            ? "checkbox"
                            : "radio"
                        }
                        name={`q-${q.id}`}
                        checked={(
                          answers[q.id]?.selected_options || []
                        ).includes(o.id)}
                        onChange={(e) => {
                          const previous =
                            answers[q.id]?.selected_options || [];
                          const selected =
                            q.question_type === "MULTIPLE_CHOICE"
                              ? e.target.checked
                                ? [...previous, o.id]
                                : previous.filter((x) => x !== o.id)
                              : [o.id];
                          setAnswers({
                            ...answers,
                            [q.id]: { selected_options: selected },
                          });
                        }}
                      />
                      <span>{o.text}</span>
                    </label>
                  ))}
                </div>
              )}
            </article>
          ))}
          {error && <div className="knowledge-error">{error}</div>}
          <button className="learning-primary" onClick={submitTest}>
            Завершить тест
          </button>
        </section>
      </main>
    );
  if (attempt && attempt.status !== "IN_PROGRESS")
    return (
      <main className="learning-page">
        <section
          className={`result-screen ${attempt.passed ? "passed" : "failed"}`}
        >
          <div>
            {attempt.passed ? <CircleCheckBig size={56} /> : <X size={56} />}
          </div>
          <p className="eyebrow">Результат тестирования</p>
          <h1>{attempt.passed ? "Тест успешно пройден" : "Тест не пройден"}</h1>
          <strong>{attempt.score_percent}%</strong>
          <p>
            {attempt.passed
              ? "Курс завершён. Сертификат доступен в соответствующем разделе."
              : "Повторите материал и попробуйте ещё раз."}
          </p>
          <button
            onClick={() => {
              setAttempt(null);
              setSelectedCourse(null);
              setSelectedAssignment(null);
              setTabMode("results");
            }}
          >
            К результатам
          </button>
        </section>
      </main>
    );
  if (selectedCourse && selectedAssignment)
    return (
      <main className="learning-page">
        <button
          className="knowledge-back"
          onClick={() => {
            setSelectedCourse(null);
            setSelectedAssignment(null);
            setLesson(null);
          }}
        >
          <ArrowLeft size={18} /> Моё обучение
        </button>
        <section className="course-detail">
          <div className="course-banner">
            <GraduationCap size={42} />
            <span>{selectedCourse.category_name}</span>
          </div>
          <div className="course-body">
            <div className="course-title">
              <div>
                <p className="eyebrow blue">
                  {selectedCourse.is_mandatory
                    ? "Обязательный курс"
                    : "Рекомендованный курс"}
                </p>
                <h1>{selectedCourse.title}</h1>
              </div>
              <span
                className={`learning-status status-${selectedAssignment.status.toLowerCase()}`}
              >
                {selectedAssignment.status_label}
              </span>
            </div>
            <p>
              {selectedCourse.description || selectedCourse.short_description}
            </p>
            <div className="course-facts">
              <span>
                <Clock3 size={17} />
                {selectedCourse.estimated_duration_minutes} мин
              </span>
              <span>
                <FileText size={17} />
                {selectedCourse.lessons_count} урока
              </span>
              <span>
                <Award size={17} />
                Проходной балл {selectedCourse.passing_score}%
              </span>
            </div>
            <div className="learning-progress">
              <i style={{ width: `${selectedAssignment.progress_percent}%` }} />
              <span>{selectedAssignment.progress_percent}%</span>
            </div>
            <div className="course-layout">
              <section>
                <h2>Программа курса</h2>
                {selectedCourse.modules?.map((m) => (
                  <div className="course-module" key={m.id}>
                    <h3>{m.title}</h3>
                    {m.lessons.map((l) => (
                      <button
                        key={l.id}
                        className={lesson?.id === l.id ? "active" : ""}
                        onClick={() => setLesson(l)}
                      >
                        <span>
                          {completedLessons.has(l.id) ? (
                            <CircleCheckBig size={19} />
                          ) : (
                            <PlayCircle size={19} />
                          )}
                        </span>
                        <div>
                          <b>{l.title}</b>
                          <small>
                            {l.lesson_type_label} ·{" "}
                            {l.estimated_duration_minutes} мин
                          </small>
                        </div>
                      </button>
                    ))}
                  </div>
                ))}
              </section>
              <aside>
                {lesson ? (
                  <div className="lesson-view">
                    <p className="eyebrow blue">Урок</p>
                    <h2>{lesson.title}</h2>
                    <article>
                      {lesson.content ||
                        "Материал урока связан с корпоративной базой знаний."}
                    </article>
                    <button className="learning-primary" onClick={finishLesson}>
                      {lesson.requires_confirmation
                        ? "Подтвердить и завершить"
                        : "Завершить урок"}
                    </button>
                  </div>
                ) : selectedAssignment.status === "WAITING_ASSESSMENT" &&
                  assessment ? (
                  <div className="assessment-callout">
                    <Award size={34} />
                    <h2>{assessment.title}</h2>
                    <p>
                      {assessment.questions_count} вопросов ·{" "}
                      {assessment.time_limit_minutes} минут · проходной балл{" "}
                      {assessment.passing_score}%
                    </p>
                    <button className="learning-primary" onClick={beginTest}>
                      Начать тест
                    </button>
                  </div>
                ) : selectedAssignment.status === "COMPLETED" ? (
                  <div className="assessment-callout">
                    <CircleCheckBig size={40} />
                    <h2>Курс завершён</h2>
                    <p>Результат сохранён в вашем профиле.</p>
                  </div>
                ) : (
                  <div className="assessment-callout">
                    <PlayCircle size={40} />
                    <h2>Готовы начать?</h2>
                    <p>
                      Проходите уроки последовательно — прогресс сохранится
                      автоматически.
                    </p>
                    <button className="learning-primary" onClick={startCourse}>
                      {selectedAssignment.status === "IN_PROGRESS"
                        ? "Продолжить"
                        : "Начать курс"}
                    </button>
                  </div>
                )}
              </aside>
            </div>
          </div>
        </section>
      </main>
    );
  return (
    <main className="learning-page">
      <div className="learning-heading">
        <div>
          <p className="eyebrow blue">Развитие и допуски</p>
          <h1>Обучение</h1>
          <p>Курсы, тестирование и сертификаты сотрудника.</p>
        </div>
        <div className="learning-kpis">
          <span>
            <b>
              {
                assignments.filter(
                  (x) => !["COMPLETED", "CANCELLED"].includes(x.status),
                ).length
              }
            </b>
            активных
          </span>
          <span>
            <b>{assignments.filter((x) => x.status === "OVERDUE").length}</b>
            просрочено
          </span>
          <span>
            <b>{certificates.length}</b>сертификатов
          </span>
        </div>
      </div>
      <div className="knowledge-tabs">
        {(
          [
            ["my", "Моё обучение"],
            ["catalog", "Каталог"],
            ["results", "Результаты"],
            ["certificates", "Сертификаты"],
          ] as const
        ).map(([key, label]) => (
          <button
            className={tabMode === key ? "active" : ""}
            onClick={() => setTabMode(key)}
            key={key}
          >
            {label}
          </button>
        ))}
      </div>
      {error && <div className="knowledge-error">{error}</div>}
      {loading ? (
        <div className="learning-grid">
          {[1, 2, 3].map((x) => (
            <div className="learning-card skeleton" key={x} />
          ))}
        </div>
      ) : tabMode === "my" ? (
        <div className="learning-grid">
          {assignments.map((a) => {
            const c = courses.find((x) => x.id === a.course);
            return (
              <article
                className="learning-card"
                key={a.id}
                onClick={() => openAssignment(a)}
              >
                <div className="course-card-cover">
                  <GraduationCap size={29} />
                  {a.is_mandatory && <i>Обязательно</i>}
                </div>
                <div>
                  <span
                    className={`learning-status status-${a.status.toLowerCase()}`}
                  >
                    {a.status_label}
                  </span>
                  <h2>{a.course_title}</h2>
                  <p>{c?.short_description}</p>
                  <div className="mini-progress">
                    <i style={{ width: `${a.progress_percent}%` }} />
                  </div>
                  <footer>
                    <b>{a.progress_percent}%</b>
                    <span>
                      {a.due_at
                        ? `до ${new Date(a.due_at).toLocaleDateString("ru-RU")}`
                        : "без срока"}
                    </span>
                  </footer>
                </div>
              </article>
            );
          })}
        </div>
      ) : tabMode === "catalog" ? (
        <div className="learning-grid">
          {courses.map((c) => (
            <article className="learning-card" key={c.id}>
              <div className="course-card-cover catalog">
                <BookOpen size={29} />
              </div>
              <div>
                <span>{c.category_name}</span>
                <h2>{c.title}</h2>
                <p>{c.short_description}</p>
                <footer>
                  <b>{c.lessons_count} урока</b>
                  <span>{c.estimated_duration_minutes} мин</span>
                </footer>
              </div>
            </article>
          ))}
        </div>
      ) : tabMode === "results" ? (
        <section className="learning-table">
          <h2>История тестирования</h2>
          {attempts.length ? (
            attempts.map((a) => (
              <div key={a.id}>
                <span
                  className={
                    a.passed ? "result-dot passed" : "result-dot failed"
                  }
                />
                <div>
                  <b>{a.assessment_title}</b>
                  <small>Попытка {a.attempt_number}</small>
                </div>
                <strong>{a.score_percent}%</strong>
                <em>{a.status}</em>
              </div>
            ))
          ) : (
            <p>Завершённых попыток пока нет.</p>
          )}
        </section>
      ) : (
        <div className="certificate-grid">
          {certificates.length ? (
            certificates.map((c) => (
              <article className="certificate-card" key={c.id}>
                <Award size={42} />
                <p>AYS Connect</p>
                <h2>{c.course_title}</h2>
                <span>Сертификат № {c.certificate_number}</span>
                <footer>
                  <small>Действует до</small>
                  <b>
                    {c.expires_at
                      ? new Date(c.expires_at).toLocaleDateString("ru-RU")
                      : "Бессрочно"}
                  </b>
                </footer>
              </article>
            ))
          ) : (
            <section className="knowledge-empty">
              <Award size={40} />
              <h2>Сертификатов пока нет</h2>
              <p>Они появятся после успешного завершения курсов.</p>
            </section>
          )}
        </div>
      )}
    </main>
  );
}

function KnowledgeView() {
  const [materials, setMaterials] = useState<KnowledgeMaterialData[]>([]);
  const [categories, setCategories] = useState<KnowledgeCategoryData[]>([]);
  const [required, setRequired] = useState<AcknowledgmentData[]>([]);
  const [selected, setSelected] = useState<KnowledgeMaterialData | null>(null);
  const [mode, setMode] = useState<
    "catalog" | "required" | "favorites" | "recent" | "ttk"
  >("catalog");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [materialType, setMaterialType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (query) params.set("search", query);
      if (category) params.set("category", category);
      if (materialType) params.set("material_type", materialType);
      if (mode === "favorites") params.set("favorite", "true");
      let endpoint = `/knowledge/materials/?${params}`;
      if (mode === "recent") endpoint = "/knowledge/materials/recent/";
      if (mode === "ttk") endpoint = "/knowledge/materials/ttk/";
      const [materialData, categoryData, requiredData] = await Promise.all([
        api(endpoint),
        api("/knowledge/categories/"),
        api("/knowledge/materials/required/"),
      ]);
      setMaterials(
        Array.isArray(materialData) ? materialData : materialData.results || [],
      );
      setCategories(
        Array.isArray(categoryData) ? categoryData : categoryData.results || [],
      );
      setRequired(requiredData);
    } catch {
      setError("Не удалось загрузить рабочие материалы");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, [mode, category, materialType]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  async function openMaterial(id: number) {
    try {
      const data = await api(`/knowledge/materials/${id}/`);
      setSelected(data);
    } catch {
      setError("Материал недоступен");
    }
  }
  async function toggleFavorite(material: KnowledgeMaterialData) {
    const result = await api(`/knowledge/materials/${material.id}/favorite/`, {
      method: "POST",
    });
    setMaterials((items) =>
      items.map((x) =>
        x.id === material.id ? { ...x, is_favorite: result.is_favorite } : x,
      ),
    );
    setSelected((x) =>
      x?.id === material.id ? { ...x, is_favorite: result.is_favorite } : x,
    );
  }
  async function acknowledge(material: KnowledgeMaterialData) {
    try {
      await api(`/knowledge/materials/${material.id}/acknowledge/`, {
        method: "POST",
      });
      setRequired((items) =>
        items.filter((x) => x.material_id !== material.id),
      );
      setError("");
    } catch {
      setError("Ознакомление не назначено или уже недоступно");
    }
  }
  async function downloadVersion(
    material: KnowledgeMaterialData,
    version: MaterialVersionData,
  ) {
    const token = sessionStorage.getItem("access");
    const response = await fetch(
      `${API}/knowledge/materials/${material.id}/versions/${version.id}/download/`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!response.ok) {
      setError("Скачивание недоступно");
      return;
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = version.original_name || material.title;
    link.click();
    URL.revokeObjectURL(url);
  }
  const requiredIds = new Set(required.map((x) => x.material_id));
  const visible =
    mode === "required"
      ? materials.filter((x) => requiredIds.has(x.id))
      : materials;

  if (selected)
    return (
      <main className="knowledge-page">
        <button className="knowledge-back" onClick={() => setSelected(null)}>
          <ArrowLeft size={18} /> К каталогу
        </button>
        <section className="material-detail">
          <div
            className={`material-hero type-${selected.material_type.toLowerCase()}`}
          >
            <FileText size={38} />
            <span>{selected.material_type_label}</span>
          </div>
          <div className="material-main">
            <div className="material-title-row">
              <div>
                <p className="eyebrow blue">{selected.category_name}</p>
                <h1>{selected.title}</h1>
              </div>
              <button
                className={
                  selected.is_favorite ? "favorite active" : "favorite"
                }
                onClick={() => toggleFavorite(selected)}
              >
                <Star
                  size={20}
                  fill={selected.is_favorite ? "currentColor" : "none"}
                />
              </button>
            </div>
            <p className="material-description">
              {selected.description ||
                "Описание материала будет дополнено владельцем."}
            </p>
            <div className="material-meta">
              <span>
                <FileText size={16} /> Версия{" "}
                {selected.current_version?.version || "—"}
              </span>
              <span>
                <Clock3 size={16} /> Обновлён{" "}
                {new Date(selected.updated_at).toLocaleDateString("ru-RU")}
              </span>
              <span>
                <Eye size={16} /> Актуальный документ
              </span>
            </div>
            {selected.current_version?.content && (
              <article className="material-content">
                {selected.current_version.content}
              </article>
            )}
            {selected.current_version?.external_url && (
              <a
                className="knowledge-primary"
                href={selected.current_version.external_url}
                target="_blank"
                rel="noreferrer"
              >
                Открыть внешний материал
              </a>
            )}
            <div className="material-actions">
              {selected.current_version?.download_url && (
                <button
                  className="knowledge-primary"
                  onClick={() =>
                    downloadVersion(selected, selected.current_version!)
                  }
                >
                  <Download size={17} /> Скачать
                </button>
              )}
              {requiredIds.has(selected.id) && (
                <button
                  className="ack-button"
                  onClick={() => acknowledge(selected)}
                >
                  <CheckCircle2 size={17} /> Подтвердить ознакомление
                </button>
              )}
            </div>
            <section className="version-history">
              <h2>История версий</h2>
              {selected.versions?.map((version) => (
                <div key={version.id}>
                  <b>Версия {version.version}</b>
                  <span>{version.change_summary || "Первая публикация"}</span>
                  <time>
                    {new Date(version.created_at).toLocaleDateString("ru-RU")}
                  </time>
                </div>
              ))}
            </section>
          </div>
        </section>
        {error && <div className="knowledge-error">{error}</div>}
      </main>
    );
  return (
    <main className="knowledge-page">
      <div className="knowledge-heading">
        <div>
          <p className="eyebrow blue">Корпоративная библиотека</p>
          <h1>Рабочие материалы</h1>
          <p>
            Регламенты, инструкции, ТТК и техническая документация в одном
            месте.
          </p>
        </div>
        <div className="knowledge-summary">
          <b>{required.length}</b>
          <span>требуют ознакомления</span>
        </div>
      </div>
      <div className="knowledge-tabs">
        {(
          [
            ["catalog", "Все материалы"],
            ["required", "Обязательные"],
            ["favorites", "Избранное"],
            ["recent", "Недавние"],
            ["ttk", "ТТК"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            className={mode === key ? "active" : ""}
            onClick={() => setMode(key)}
          >
            {label}
            {key === "required" && required.length > 0 && (
              <i>{required.length}</i>
            )}
          </button>
        ))}
      </div>
      <section className="knowledge-tools">
        <label className="knowledge-search">
          <Search size={18} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Найти регламент, инструкцию или ТТК"
          />
        </label>
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Все категории</option>
          {categories.map((x) => (
            <option value={x.id} key={x.id}>
              {x.name}
            </option>
          ))}
        </select>
        <select
          value={materialType}
          onChange={(e) => setMaterialType(e.target.value)}
        >
          <option value="">Все типы</option>
          <option value="INSTRUCTION">Инструкции</option>
          <option value="REGULATION">Регламенты</option>
          <option value="PDF">PDF</option>
          <option value="PRESENTATION">Презентации</option>
          <option value="TECHNICAL_DOCUMENTATION">
            Техническая документация
          </option>
          <option value="HACCP">ХАССП</option>
          <option value="TTK">ТТК</option>
        </select>
      </section>
      {error && <div className="knowledge-error">{error}</div>}
      {loading ? (
        <div className="knowledge-grid">
          {[1, 2, 3, 4, 5, 6].map((x) => (
            <div className="material-card skeleton" key={x} />
          ))}
        </div>
      ) : visible.length ? (
        <div className="knowledge-grid">
          {visible.map((material) => (
            <article
              className="material-card"
              key={material.id}
              onClick={() => openMaterial(material.id)}
            >
              <div
                className={`material-cover type-${material.material_type.toLowerCase()}`}
              >
                <FileText size={28} />
                <span>{material.material_type_label}</span>
                {material.is_required && <i>Обязательно</i>}
              </div>
              <div className="material-card-body">
                <div className="material-card-top">
                  <span>{material.category_name}</span>
                  <button
                    aria-label="Избранное"
                    className={material.is_favorite ? "active" : ""}
                    onClick={(e) => {
                      e.stopPropagation();
                      void toggleFavorite(material);
                    }}
                  >
                    <Star
                      size={17}
                      fill={material.is_favorite ? "currentColor" : "none"}
                    />
                  </button>
                </div>
                <h2>{material.title}</h2>
                <p>
                  {material.description || "Корпоративный рабочий материал"}
                </p>
                <footer>
                  <span>Версия {material.current_version?.version || "—"}</span>
                  <time>
                    {new Date(material.updated_at).toLocaleDateString("ru-RU")}
                  </time>
                </footer>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <section className="knowledge-empty">
          <BookOpen size={40} />
          <h2>Материалы не найдены</h2>
          <p>Измените фильтры или поисковый запрос.</p>
          <button
            onClick={() => {
              setQuery("");
              setCategory("");
              setMaterialType("");
              setMode("catalog");
            }}
          >
            Сбросить фильтры
          </button>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
