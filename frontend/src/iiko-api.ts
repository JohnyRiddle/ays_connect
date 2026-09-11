export type CardCheckResult = {
  connectionId: string;
  organizationId: string;
  card: string;
  customerId: string;
  owner?: { surname: string; name: string; patronymic: string };
  comment?: string;
  cards: { id: string | null; number: string }[];
  categories: { id: string; name?: string; isActive?: boolean }[];
  walletBalances: { id: string; name?: string; type?: number; balance?: number }[];
};

export async function checkIikoCard(number: string, signal: AbortSignal): Promise<CardCheckResult> {
  const token = sessionStorage.getItem("access");
  if (!token) throw new Error("Войдите в AYS Connect, чтобы проверить карту.");
  const api = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
  const response = await fetch(`${api}/iiko/connections/sheregesh/card/check/`, {
    method: "POST", signal, cache: "no-store",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ cardNumber: number.trim() }),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    // Do not surface arbitrary server bodies (which could contain diagnostic data).
    const messages: Record<number, string> = {
      400: "Проверьте номер карты: он не должен быть пустым или содержать управляющие символы.",
      401: "Сессия истекла. Войдите в AYS Connect заново.",
      403: "Нет права проверки карт Шерегеша. Обратитесь к администратору.",
      404: "Подключение Шерегеша недоступно.",
      429: "Проверка уже выполняется или достигнут лимит запросов. Повторите позже.",
      503: "Подключение временно недоступно. Обратитесь к администратору.",
    };
    const codes: Record<string, string> = {
      card_not_found: "Карта с этим номером не зарегистрирована в iiko.",
      bad_request: "iiko не смог обработать номер. Проверьте его; отсутствие карты не подтверждено.",
      not_found_unconfirmed: "iiko не вернул карту. Проверьте номер; отсутствие карты не подтверждено.",
      customer_not_returned_unconfirmed: "iiko не вернул владельца. Отсутствие карты не подтверждено.",
      authentication_failed: "Не удалось авторизовать подключение iiko. Обратитесь к администратору.",
      access_denied: "Ключ iiko не разрешает чтение карты. Обратитесь к администратору.",
    };
    throw new Error(messages[response.status] || codes[body?.error?.code] || "Не удалось получить ответ iiko. Повторите проверку позже.");
  }
  if (!body || typeof body.customerId !== "string" || typeof body.card !== "string" ||
    body.connectionId !== "sheregesh" || !Array.isArray(body.cards) ||
    !Array.isArray(body.categories) || !Array.isArray(body.walletBalances)) {
    throw new Error("Получен неполный ответ. Повторите проверку позже.");
  }
  return body;
}

export type CardCreationResult = {
  operationId: string; status: "running" | "succeeded" | "failed" | "needs_review";
  stage: string; customerId: string | null; completedCategories: string[]; errorCode: string;
  httpStatus?: number | null; correlationId?: string | null;
  diagnostics?: { endpoint?: string; fields?: Record<string, string> }; updatedAt?: string;
  errorHint?: string; topupAmount?: string | null; topupConfirmed?: boolean;
};

export class CardCreationError extends Error {
  constructor(message: string, public readonly uncertain: boolean) { super(message); }
}

export async function createIikoCard(data: Record<string, string>): Promise<CardCreationResult> {
  return creationRequest("create/", data);
}

export async function getIikoCardCreation(id: string): Promise<CardCreationResult> {
  return creationRequest(`operations/${encodeURIComponent(id)}/`);
}

async function creationRequest(path: string, data?: Record<string, string>): Promise<CardCreationResult> {
  const token = sessionStorage.getItem("access");
  if (!token) throw new CardCreationError("Войдите в AYS Connect.", false);
  const api = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
  let response: Response;
  try {
    response = await fetch(`${api}/iiko/connections/sheregesh/card/${path}`, {
      method: data ? "POST" : "GET", cache: "no-store", signal: AbortSignal.timeout(180000),
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      ...(data ? { body: JSON.stringify(data) } : {}),
    });
  } catch {
    throw new CardCreationError("Связь прервалась. Запрос мог выполниться. Обновите статус операции перед дальнейшими действиями.", true);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const messages: Record<number, string> = {
      400: "Проверьте ФИО, номер и все четыре категории.",
      401: "Сессия истекла. Войдите заново.",
      403: "Нет права создания карт Шерегеша.",
      404: "Операция не найдена. Можно заполнить новую форму.",
      409: "Номер уже участвует в операции или данные повторного запроса изменились. Проверьте карту.",
      429: "Другая операция уже выполняется или достигнут лимит запросов. Повторите позже.",
    };
    const codes: Record<string, string> = {
      anonymous_single_card: "iiko уже запретил удаление единственной карты анонимного гостя. Требуется разбор регистрации прежнего гостя; повторная передача заблокирована.",
      confirmation_changed: "Данные карты или совпадения ФИО изменились. Проверьте форму заново.",
      confirmation_expired: "Подтверждение истекло. Проверьте форму заново.",
      replacement_confirmation_required: "Подтвердите снятие регистрации после проверки прежнего владельца.",
      duplicate_confirmation_required: "Проверьте совпадения ФИО и подтвердите создание отдельного гостя.",
    };
    throw new CardCreationError(codes[body?.error?.code] || messages[response.status] || "Операция не завершена. Обновите статус и проверьте карту.", response.status >= 500 || (!data && response.status !== 404));
  }
  if (!body || typeof body.operationId !== "string" || !["running", "succeeded", "failed", "needs_review"].includes(body.status)) {
    throw new CardCreationError("Неполный ответ. Обновите статус операции.", true);
  }
  return body;
}


export type CardCatalog = {
  connectionId: string; organizationId: string;
  fields: Record<"department" | "legalEntity" | "cardType" | "approval", { id: string; name: string }[]>;
};

export async function getIikoCardCatalog(signal: AbortSignal): Promise<CardCatalog> {
  const api = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
  const response = await fetch(`${api}/iiko/connections/sheregesh/card/catalog/`, {
    cache: "no-store", signal, headers: { Authorization: `Bearer ${sessionStorage.getItem("access") || ""}` },
  });
  if (!response.ok) throw new Error("Не удалось загрузить справочники карт. Проверьте вход и права доступа.");
  const body = await response.json();
  if (body?.connectionId !== "sheregesh" || body.organizationId !== "07727ae8-4b93-4529-ac85-9232fae45be3" ||
      !["department", "legalEntity", "cardType", "approval"].every(field => Array.isArray(body.fields?.[field]) &&
        body.fields[field].length > 0 && body.fields[field].every((item: { id?: unknown; name?: unknown }) => typeof item.id === "string" && typeof item.name === "string"))) {
    throw new Error("Справочники карт не настроены для этой локации.");
  }
  return body;
}


export type GuestSummary = {
  comment?: string;
  customerId: string; owner: { surname: string; name: string; patronymic: string };
  cards: { id: string; number: string }[];
  categories: { id: string; name?: string; isActive?: boolean }[];
  walletBalances: { id: string; name?: string; balance?: number; type?: number }[];
};
export type CardPreparation = {
  confirmationToken: string; existingCard: GuestSummary | null; duplicates: GuestSummary[];
  incomplete: boolean; limited: boolean; coverage: string; canReplace: boolean;
};

export async function prepareIikoCard(data: Record<string, string>, signal: AbortSignal): Promise<CardPreparation> {
  const api = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
  const response = await fetch(`${api}/iiko/connections/sheregesh/card/prepare/`, {
    method: "POST", cache: "no-store", signal,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${sessionStorage.getItem("access") || ""}` },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    if (error?.error?.code === "anonymous_single_card") throw new Error("iiko уже запретил удаление единственной карты анонимного гостя. Требуется разбор регистрации прежнего гостя; повторная передача заблокирована.");
    throw new Error(response.status === 401 ? "Войдите в AYS Connect заново." : response.status === 403 ? "Нет права оформления карт." : "Не удалось проверить карту и совпадения ФИО. Попробуйте позже.");
  }
  const body = await response.json();
  if (!body || typeof body.confirmationToken !== "string" || !Array.isArray(body.duplicates)) throw new Error("Неполный ответ предварительной проверки.");
  return body;
}
