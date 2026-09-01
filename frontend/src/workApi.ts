const API_ROOT = (
  import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"
).replace(/\/api\/v1\/?$/, "/api/internal/v1");
const AUTH_ROOT = (
  import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"
).replace(/\/$/, "");

export type ApiErrorKind =
  | "validation"
  | "unauthenticated"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "throttled"
  | "server"
  | "network";

export class WorkApiError extends Error {
  constructor(
    public kind: ApiErrorKind,
    message: string,
    public status = 0,
    public fields: Record<string, string[]> = {},
    public requestId = "",
  ) {
    super(message);
  }
}

function messageFromPayload(payload: unknown): string {
  if (!payload || typeof payload !== "object")
    return "Не удалось выполнить запрос.";
  const data = payload as Record<string, unknown>;
  const candidate = data.detail || data.message || data.error || data.code;
  if (typeof candidate === "string") return candidate;
  for (const value of Object.values(data)) {
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
    if (typeof value === "string") return value;
  }
  return "Не удалось выполнить запрос.";
}

async function refreshAccess(): Promise<boolean> {
  const refresh = sessionStorage.getItem("refresh");
  if (!refresh) return false;
  const response = await fetch(`${AUTH_ROOT}/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!response.ok) return false;
  const data = await response.json();
  sessionStorage.setItem("access", data.access);
  if (data.refresh) sessionStorage.setItem("refresh", data.refresh);
  return true;
}

export async function workRequest<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const token = sessionStorage.getItem("access");
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      ...options,
      headers: {
        ...(!(options.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new WorkApiError("network", "Нет соединения с сервером.");
  }
  if (response.status === 401 && retry && (await refreshAccess()))
    return workRequest<T>(path, options, false);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const fields: Record<string, string[]> = {};
    if (payload && typeof payload === "object")
      for (const [key, value] of Object.entries(payload))
        if (Array.isArray(value)) fields[key] = value.map(String);
    const kinds: Record<number, ApiErrorKind> = {
      400: "validation",
      401: "unauthenticated",
      403: "forbidden",
      404: "not_found",
      409: "conflict",
      429: "throttled",
    };
    const kind = kinds[response.status] || "server";
    if (kind === "unauthenticated") sessionStorage.clear();
    const defaults: Record<ApiErrorKind, string> = {
      validation: "Проверьте заполнение формы.",
      unauthenticated: "Сессия завершена. Войдите снова.",
      forbidden: "Недостаточно прав для выполнения операции.",
      not_found: "Объект недоступен или не найден.",
      conflict: "Объект был изменён другим пользователем.",
      throttled: "Слишком много запросов. Повторите позже.",
      server: "Ошибка сервера.",
      network: "Нет соединения с сервером.",
    };
    throw new WorkApiError(
      kind,
      messageFromPayload(payload) || defaults[kind],
      response.status,
      fields,
      response.headers.get("X-Request-ID") || "",
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function workDownload(
  path: string,
  filename: string,
  retry = true,
): Promise<void> {
  const token = sessionStorage.getItem("access");
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch {
    throw new WorkApiError("network", "Нет соединения с сервером.");
  }
  if (response.status === 401 && retry && (await refreshAccess()))
    return workDownload(path, filename, false);
  if (!response.ok)
    throw new WorkApiError(
      response.status === 403 ? "forbidden" : "server",
      response.status === 403
        ? "Недостаточно прав для скачивания файла."
        : "Не удалось скачать файл.",
      response.status,
    );
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
export type AssignmentTarget = {
  id: string;
  target_type: string;
  target_type_label: string;
  display_name: string;
};

export const tasksApi = {
  list: (query = "") =>
    workRequest<Page<any>>(`/tasks/${query ? `?${query}` : ""}`),
  get: (id: string) => workRequest<any>(`/tasks/${id}/`),
  create: (data: unknown) =>
    workRequest<any>("/tasks/", { method: "POST", body: JSON.stringify(data) }),
  action: (id: string, action: string, data: unknown) =>
    workRequest<any>(`/tasks/${id}/${action}/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  comments: (id: string) => workRequest<any[]>(`/tasks/${id}/comments/`),
  addComment: (id: string, data: unknown) =>
    workRequest<any>(`/tasks/${id}/comments/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  attachments: (id: string) => workRequest<any[]>(`/tasks/${id}/attachments/`),
  upload: (id: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return workRequest<any>(`/tasks/${id}/attachments/`, {
      method: "POST",
      body,
    });
  },
  download: (id: string, attachmentId: string, filename: string) =>
    workDownload(
      `/tasks/${id}/attachments/${attachmentId}/download/`,
      filename,
    ),
  watchers: (id: string) => workRequest<any[]>(`/tasks/${id}/watchers/`),
  watch: (id: string, remove = false) =>
    workRequest<any>(`/tasks/${id}/watch/`, {
      method: remove ? "DELETE" : "POST",
    }),
  checklists: (id: string) => workRequest<any[]>(`/tasks/${id}/checklists/`),
  toggleItem: (
    id: string,
    checklist: string,
    item: string,
    complete: boolean,
  ) =>
    workRequest<any>(
      `/tasks/${id}/checklists/${checklist}/items/${item}/${complete ? "complete" : "uncomplete"}/`,
      { method: "POST", body: "{}" },
    ),
  activity: (id: string) =>
    workRequest<any>(`/tasks/${id}/activity/?page_size=25`),
};

export const requestsApi = {
  catalog: () => workRequest<any[]>("/service-catalog/"),
  schema: (id: string) => workRequest<any>(`/request-types/${id}/form-schema/`),
  list: (query = "") =>
    workRequest<Page<any>>(`/requests/${query ? `?${query}` : ""}`),
  get: (id: string) => workRequest<any>(`/requests/${id}/`),
  createTask: (id: string, data: unknown) =>
    workRequest<any>(`/requests/${id}/tasks/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  create: (data: unknown) =>
    workRequest<any>("/requests/", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  action: (id: string, action: string, data: unknown) =>
    workRequest<any>(`/requests/${id}/${action}/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  comments: (id: string) => workRequest<any[]>(`/requests/${id}/comments/`),
  addComment: (id: string, data: unknown) =>
    workRequest<any>(`/requests/${id}/comments/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  attachments: (id: string) =>
    workRequest<any[]>(`/requests/${id}/attachments/`),
  upload: (id: string, file: File, visibility: string) => {
    const body = new FormData();
    body.append("file", file);
    body.append("visibility", visibility);
    return workRequest<any>(`/requests/${id}/attachments/`, {
      method: "POST",
      body,
    });
  },
  download: (id: string, attachmentId: string, filename: string) =>
    workDownload(
      `/requests/${id}/attachments/${attachmentId}/download/`,
      filename,
    ),
  watchers: (id: string) => workRequest<any[]>(`/requests/${id}/watchers/`),
  watch: (id: string, remove = false) =>
    workRequest<any>(`/requests/${id}/watch/`, {
      method: remove ? "DELETE" : "POST",
    }),
  activity: (id: string) =>
    workRequest<any>(`/requests/${id}/activity/?page_size=25`),
  history: (id: string) => workRequest<any>(`/requests/${id}/history/`),
  sla: (id: string) => workRequest<any>(`/requests/${id}/sla/`),
};

export const lookupApi = {
  targets: (search = "") =>
    workRequest<Page<AssignmentTarget>>(
      `/assignment-targets/?search=${encodeURIComponent(search)}`,
    ),
  employees: (search = "") =>
    workRequest<Page<any>>(`/employees/?search=${encodeURIComponent(search)}`),
  orgUnits: () => workRequest<Page<any>>("/org-units/"),
  legalEntities: () => workRequest<Page<any>>("/legal-entities/"),
  locations: () => workRequest<Page<any>>("/locations/"),
};
