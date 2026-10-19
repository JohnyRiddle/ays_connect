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
  const nestedError = data.error;
  if (nestedError && typeof nestedError === "object") {
    const nested = nestedError as Record<string, unknown>;
    if (typeof nested.message === "string") return nested.message;
    if (typeof nested.detail === "string") return nested.detail;
  }
  const candidate = data.detail || data.message || data.error || data.code;
  if (typeof candidate === "string") return candidate;
  for (const value of Object.values(data)) {
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
    if (typeof value === "string") return value;
  }
  return "Не удалось выполнить запрос.";
}

// Refresh belongs to the session, not any one polling request. Share it across
// callers, but give each caller independent cancellation and bound the refresh.
let refreshPending: { token: string; promise: Promise<boolean> } | null = null;
function refreshAccess(): Promise<boolean> {
  const refresh = sessionStorage.getItem("refresh");
  if (refreshPending?.token === refresh) return refreshPending.promise;
  if (!refresh) return Promise.resolve(false);
  const controller = new AbortController();
  let timeout: ReturnType<typeof setTimeout>;
  const expired = new Promise<never>((_, reject) => {
    timeout = setTimeout(() => {
      controller.abort();
      reject(new WorkApiError("network", "Не удалось обновить сессию. Повторите запрос."));
    }, 15000);
  });
  const request = (async () => {
    try {
      const response = await fetch(`${AUTH_ROOT}/auth/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
        signal: controller.signal,
      });
      if ([401, 403].includes(response.status)) return false;
      if (!response.ok) throw new WorkApiError("network", "Не удалось обновить сессию. Повторите запрос.");
      const data = await response.json();
      // Never restore a logged-out session or overwrite a newer login.
      if (controller.signal.aborted || sessionStorage.getItem("refresh") !== refresh) return false;
      if (typeof data.access !== "string" || !data.access)
        throw new WorkApiError("network", "Некорректный ответ обновления сессии.");
      sessionStorage.setItem("access", data.access);
      if (typeof data.refresh === "string" && data.refresh) sessionStorage.setItem("refresh", data.refresh);
      return true;
    } catch (error) {
      if (error instanceof WorkApiError) throw error;
      throw new WorkApiError("network", "Не удалось обновить сессию. Повторите запрос.");
    }
  })();
  const promise = Promise.race([request, expired]).finally(() => {
    clearTimeout(timeout);
    if (refreshPending?.promise === promise) refreshPending = null;
  });
  refreshPending = { token: refresh, promise };
  return promise;
}

function waitForRefresh(signal?: AbortSignal | null): Promise<boolean> {
  if (signal?.aborted) return Promise.reject(new WorkApiError("network", "Запрос отменён."));
  const pending = refreshAccess();
  if (!signal) return pending;
  return new Promise((resolve, reject) => {
    const aborted = () => reject(new WorkApiError("network", "Запрос отменён."));
    signal.addEventListener("abort", aborted, { once: true });
    pending.then(resolve, reject).finally(() => signal.removeEventListener("abort", aborted));
  });
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
  if (response.status === 401 && retry) {
    // Another request may already have rotated the token while this was in flight.
    const current = sessionStorage.getItem("access");
    if ((current && current !== token) || (await waitForRefresh(options.signal)))
      return workRequest<T>(path, options, false);
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const fields: Record<string, string[]> = {};
    const fieldPayload = payload?.error?.details || payload;
    if (fieldPayload && typeof fieldPayload === "object")
      for (const [key, value] of Object.entries(fieldPayload))
        if (Array.isArray(value)) fields[key] = value.map(String);
        else if (typeof value === "string") fields[key] = [value];
    const kinds: Record<number, ApiErrorKind> = {
      400: "validation",
      401: "unauthenticated",
      403: "forbidden",
      404: "not_found",
      409: "conflict",
      429: "throttled",
    };
    const kind = kinds[response.status] || "server";
    if (kind === "unauthenticated" && sessionStorage.getItem("access") === token) {
      sessionStorage.removeItem("access");
      sessionStorage.removeItem("refresh");
    }
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
  preview?: (url:string)=>void,
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
  if (response.status === 401 && retry) {
    const current = sessionStorage.getItem("access");
    if ((current && current !== token) || (await refreshAccess()))
      return workDownload(path, filename, false, preview);
  }
  if (!response.ok)
    throw new WorkApiError(
      response.status === 403 ? "forbidden" : "server",
      response.status === 403
        ? "Недостаточно прав для скачивания файла."
        : "Не удалось скачать файл.",
      response.status,
    );
  const blob=await response.blob();
  const url = URL.createObjectURL(blob);
  if(preview){
    if(!['image/png','image/jpeg','image/gif','image/webp'].includes(blob.type.split(';')[0])){URL.revokeObjectURL(url);throw new WorkApiError('validation','Для этого файла доступно только скачивание.');}
    preview(url);return;
  }
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
  comments: (id: string, signal?: AbortSignal) => workRequest<any[]>(`/tasks/${id}/comments/`, { signal }),
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
  preview: (id:string, attachmentId:string, onPreview:(url:string)=>void)=>workDownload(`/tasks/${id}/attachments/${attachmentId}/download/`, '', true, onPreview),
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
  preview: (id:string, attachmentId:string, onPreview:(url:string)=>void)=>workDownload(`/tasks/${id}/attachments/${attachmentId}/download/`, '', true, onPreview),
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
  locations: async (signal?: AbortSignal): Promise<Page<any>> => {
    const results = new Map<string, any>();
    for (let page = 1; page <= 1000; page++) {
      const data = await workRequest<Page<any>>(`/locations/${page === 1 ? '' : `?page=${page}`}`, {signal});
      for (const location of data.results) results.set(location.id, location);
      if (!data.next) return {count: results.size, next: null, previous: null, results: [...results.values()]};
    }
    throw new WorkApiError('server', 'Не удалось загрузить полный список объектов. Повторите попытку.');
  },
};

