import React, { useEffect, useRef, useState } from "react";
import { CreditCard, Plus, Search, Trash2, MapPin, ArrowLeft, CheckCircle2 } from "lucide-react";
import "./iiko-cards.css";
import { prepareIikoCard, type CardPreparation, type GuestSummary, getIikoCardCatalog, type CardCatalog, checkIikoCard, createIikoCard, getIikoCardCreation, CardCreationError, type CardCreationResult, type CardCheckResult } from "./iiko-api";

// User-approved reference categories, read from the pilot guest on 2026-09-10.
// IDs are scoped to this connection/organization, never global directory IDs.
const reference = {
  connectionId: "sheregesh",
  organizationId: "07727ae8-4b93-4529-ac85-9232fae45be3",
  fields: [
    { key: "legalEntity", label: "Юридическое лицо", id: "f35f4f62-e37f-4b5f-a9bf-73eac924d12b", name: "ООО Аэроотель" },
    { key: "department", label: "Подразделение", id: "43d6f832-f4e0-4659-877f-5724c5727d60", name: "IT" },
    { key: "cardType", label: "Тип карты", id: "12db95b7-3f4d-4ba7-9776-0577ad788986", name: "Карта питания" },
    { key: "approval", label: "Согласование", id: "df9c9d05-e1e5-412e-9666-03f371e49d76", name: "Без согласования" },
  ],
} as const;
type CategoryField = typeof reference.fields[number]["key"];
type Draft = { surname: string; name: string; patronymic: string; cardNumber: string; topupAmount: string; comment: string } & Record<CategoryField, string>;
const emptyDraft: Draft = {
  surname: "", name: "", patronymic: "", cardNumber: "", comment: "", topupAmount: "10000",
  legalEntity: reference.fields[0].id, department: reference.fields[1].id,
  cardType: reference.fields[2].id, approval: reference.fields[3].id,
};

export default function IikoCardsPage() {
  const [catalog, setCatalog] = useState<CardCatalog | null>(null);
  const [catalogMessage, setCatalogMessage] = useState("");
  const [catalogVersion, setCatalogVersion] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setCatalogMessage("");
    getIikoCardCatalog(controller.signal).then(setCatalog).catch((error) => {
      if (!controller.signal.aborted) setCatalogMessage(error instanceof Error ? error.message : "Справочники недоступны.");
    });
    return () => controller.abort();
  }, [catalogVersion]);
  const optionsFor = (key: CategoryField) => catalog?.fields[key] || reference.fields.filter(field => field.key === key);
  const [tab, setTab] = useState<"create" | "check">("create");
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [review, setReview] = useState(false);
  const [preparation, setPreparation] = useState<CardPreparation | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [confirmReplacement, setConfirmReplacement] = useState(false);
  const [confirmDuplicates, setConfirmDuplicates] = useState(false);
  const preparedId = useRef<string | null>(null);
  const previewPending = useRef<AbortController | null>(null);
  useEffect(() => () => previewPending.current?.abort(), []);
  const [creation, setCreation] = useState<CardCreationResult | null>(null);
  const [creating, setCreating] = useState(false);
  const [creationMessage, setCreationMessage] = useState("");
  const [operationId, setOperationId] = useState<string | null>(() => sessionStorage.getItem("iiko.creation.operation"));
  const sending = useRef(false);
  const creationLocked = !catalog || preparing || creating || Boolean(operationId && creation?.status !== "failed");
  const saveOperation = (id: string | null) => {
    setOperationId(id);
    if (id) sessionStorage.setItem("iiko.creation.operation", id);
    else sessionStorage.removeItem("iiko.creation.operation");
  };
  const acceptCreation = (value: CardCreationResult) => {
    setCreation(value); setCreationMessage("");
    if (value.status === "failed") { setReview(false); setPreparation(null); }
  };
  const refreshCreation = async (id: string) => {
    if (sending.current) return;
    sending.current = true; setCreating(true);
    try { acceptCreation(await getIikoCardCreation(id)); }
    catch (error) {
      setCreationMessage(error instanceof Error ? error.message : "Не удалось обновить статус.");
      if (error instanceof CardCreationError && !error.uncertain) { saveOperation(null); setReview(false); setPreparation(null); }
    } finally { sending.current = false; setCreating(false); }
  };
  useEffect(() => {
    const id = sessionStorage.getItem("iiko.creation.operation");
    if (id) void refreshCreation(id);
  }, []);
  const prepare = async (event: React.FormEvent) => {
    event.preventDefault();
    if (creationLocked || previewPending.current) return;
    setReview(false); setPreparation(null); setCreation(null); saveOperation(null); setCreationMessage(""); setConfirmReplacement(false); setConfirmDuplicates(false);
    const controller = new AbortController(); previewPending.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), 120000);
    setPreparing(true); const id = crypto.randomUUID();
    try {
      const value = await prepareIikoCard({ ...draft, operationId: id }, controller.signal);
      if (previewPending.current === controller) { setPreparation(value); preparedId.current = id; setReview(true); }
    } catch (error) {
      if (previewPending.current === controller) setCreationMessage(controller.signal.aborted ? "Предварительная проверка заняла слишком много времени. Повторите позже." : error instanceof Error ? error.message : "Проверка недоступна.");
    } finally {
      window.clearTimeout(timeout);
      if (previewPending.current === controller) { previewPending.current = null; setPreparing(false); }
    }
  };
  const requiresDuplicateConfirmation = Boolean(preparation && (preparation.duplicates.length || preparation.incomplete || preparation.limited));
  const confirmationMissing = Boolean(!preparation || (preparation.existingCard && (!confirmReplacement || !preparation.canReplace)) || (requiresDuplicateConfirmation && !confirmDuplicates));
  const create = async () => {
    if (sending.current || creationLocked || !review || confirmationMissing || !preparedId.current || !preparation) return;
    sending.current = true; setCreating(true); setCreationMessage(""); setCreation(null);
    const id = preparedId.current; saveOperation(id);
    try {
      acceptCreation(await createIikoCard({ ...draft, operationId: id, confirmationToken: preparation.confirmationToken,
        confirmReplacement: confirmReplacement ? "yes" : "", confirmDuplicates: confirmDuplicates ? "yes" : "" }));
    } catch (error) {
      setCreationMessage(error instanceof Error ? error.message : "Не удалось получить результат создания.");
      if (error instanceof CardCreationError && !error.uncertain) { saveOperation(null); setReview(false); setPreparation(null); }
    } finally { sending.current = false; setCreating(false); }
  };
  const [number, setNumber] = useState("");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<CardCheckResult | null>(null);
  const [checking, setChecking] = useState(false);
  const matchesReferenceScope = result?.connectionId === reference.connectionId && result?.organizationId === reference.organizationId;
  const cardEntities = reference.fields.map((field) => ({
    ...field,
    category: matchesReferenceScope ? (() => {
      const categories = result?.categories.filter(category => optionsFor(field.key).some(option => option.id === category.id)) || [];
      return categories.length ? { name: categories.map(category => category.name || "Без названия").join(", "), isActive: categories.every(category => category.isActive !== false) } : undefined;
    })() : undefined,
  }));
  const otherCategories = result?.categories.filter((category) =>
    !matchesReferenceScope || !reference.fields.some((field) => optionsFor(field.key).some(option => option.id === category.id))) || [];
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => { pending.current?.abort(); pending.current = null; }, []);
  const clearCheck = () => {
    pending.current?.abort(); pending.current = null;
    setChecking(false); setResult(null); setMessage("");
  };
  const check = async (event: React.FormEvent) => {
    event.preventDefault(); clearCheck();
    const controller = new AbortController(); pending.current = controller;
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, 90000);
    setChecking(true);
    try {
      const response = await checkIikoCard(number, controller.signal);
      if (pending.current === controller) setResult(response);
    } catch (error) {
      if (pending.current === controller) {
        setMessage(timedOut ? "Проверка заняла слишком много времени. Повторите позже."
          : error instanceof TypeError ? "Не удалось связаться с сервером. Проверьте соединение."
          : error instanceof Error ? error.message : "Проверка временно недоступна.");
      }
    } finally {
      window.clearTimeout(timeout);
      if (pending.current === controller) { pending.current = null; setChecking(false); }
    }
  };
  const update = (key: keyof Draft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value, ...(key === "cardType" ? { topupAmount: value === reference.fields[2].id ? "10000" : "" } : {}) }));
    setReview(false); setPreparation(null); setConfirmReplacement(false); setConfirmDuplicates(false); setCreation(null); setCreationMessage(""); saveOperation(null);
  };

  const guestDetails = (guest: GuestSummary) => <div className="iiko-reviewed-guest">
    <p><b>{[guest.owner.surname, guest.owner.name, guest.owner.patronymic].filter(Boolean).join(" ") || "ФИО не указано"}</b></p>
    <p className="iiko-owner-id">ID гостя: {guest.customerId}</p>
    <p>Карты владельца: {guest.cards.map(card => card.number).join(", ") || "Нет"}</p>
    <p className="iiko-comment"><b>Комментарий:</b> {guest.comment || "Не указан"}</p>
    <dl className="iiko-review-categories">{reference.fields.map(field => <div key={field.key}>
      <dt>{field.label}</dt><dd>{guest.categories.filter(category => optionsFor(field.key).some(option => option.id === category.id)).map(category => category.name || "Без названия").join(", ") || "Не указано"}</dd>
    </div>)}</dl>
    <p>Все категории: {guest.categories.map(category => (category.name || "Без названия") + (category.isActive === false ? " (неактивна)" : "")).join(", ") || "Нет"}</p>
    <p>Балансы: {guest.walletBalances.map(wallet => `${wallet.name || "Кошелёк"}: ${wallet.balance ?? "не указан"}`).join("; ") || "Нет кошельков"}</p>
  </div>;

  return <main className="iiko-page">
    <div className="iiko-heading">
      <div><p className="eyebrow blue">Сотрудники · iikoCard</p><h1>Карты сотрудников</h1>
        <p>Оформление карты и проверка её регистрации.</p></div>
      <span className="iiko-location"><MapPin size={16} /> Шерегеш</span>
    </div>

    <div className="iiko-layout">
      <section className="iiko-form-card" aria-label="Работа с картами">
        <div className="iiko-tabs" role="tablist" aria-label="Операция с картой">
          {([['create', 'Создание карты', Plus], ['check', 'Проверка карты', Search]] as const).map(([id, label, Icon]) =>
            <button key={id} id={`iiko-tab-${id}`} type="button" role="tab" aria-selected={tab === id}
              aria-controls={`iiko-panel-${id}`} tabIndex={tab === id ? 0 : -1}
              onClick={() => { setTab(id); clearCheck(); }}
              onKeyDown={(event) => {
                if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
                  event.preventDefault();
                  const next = event.key === "Home" ? "create" : event.key === "End" ? "check" : tab === "create" ? "check" : "create";
                  setTab(next); clearCheck(); document.getElementById(`iiko-tab-${next}`)?.focus();
                }
              }}><Icon size={18} />{label}</button>)}
        </div>

        <div role="tabpanel" id="iiko-panel-create" aria-labelledby="iiko-tab-create" hidden={tab !== "create"}>
          <form className="iiko-form" autoComplete="off" onSubmit={prepare}>
            {!catalog && <p className="iiko-feedback" role="status">{catalogMessage || "Загружаем справочники…"}</p>}
            {catalogMessage && <button type="button" className="iiko-secondary" onClick={() => setCatalogVersion(value => value + 1)}>Загрузить справочники</button>}
            <fieldset className="iiko-creation-fields" disabled={creationLocked}>
            <div className="iiko-section-title"><span>01</span><div><h2>Получатель карты</h2><p>Укажите сотрудника, которому будет передана карта.</p></div></div>
            <div className="iiko-fields">
              <label>Фамилия <span aria-hidden="true">*</span><input required pattern=".*\S.*" maxLength={100} value={draft.surname} onChange={(e) => update("surname", e.target.value)} placeholder="Фамилия сотрудника" /></label>
              <label>Имя <span aria-hidden="true">*</span><input required pattern=".*\S.*" maxLength={100} value={draft.name} onChange={(e) => update("name", e.target.value)} placeholder="Имя сотрудника" /></label>
              <label className="iiko-wide">Отчество <small>Необязательно</small><input maxLength={100} value={draft.patronymic} onChange={(e) => update("patronymic", e.target.value)} placeholder="Отчество сотрудника" /></label>
            </div>
            <div className="iiko-section-title"><span>02</span><div><h2>Параметры карты</h2><p>Номер указан на физической карте. Код считывания совпадает с номером, как у эталонной карты.</p></div></div>
            <div className="iiko-fields">
              <label className="iiko-wide">Номер карты <span aria-hidden="true">*</span><input required pattern=".*\S.*" maxLength={256} value={draft.cardNumber} onChange={(e) => update("cardNumber", e.target.value)} placeholder="Введите номер карты" spellCheck={false} /></label>
              <label>Сумма пополнения, ₽ <span aria-hidden="true">*</span><input type="number" required min="0.01" max={draft.cardType === reference.fields[2].id ? "10000" : "9999999999.99"} step="0.01" value={draft.topupAmount} onChange={e => update("topupAmount", e.target.value)} /><small>Кошелёк AYS Sheregesh. {draft.cardType === reference.fields[2].id ? "Для карты питания — не более 10 000 ₽." : "Укажите сумму пополнения."}</small></label>
              <label className="iiko-wide">Комментарий <small>Необязательно</small><textarea rows={4} maxLength={2000} value={draft.comment} onChange={(e) => update("comment", e.target.value)} placeholder="Дополнительная информация" /><small>Сохраняется в поле «Комментарий» гостя iikoCard. До 2000 символов.</small></label>
            </div>
            <div className="iiko-section-title"><span>03</span><div><h2>Данные по регламенту</h2><p>Выберите подразделение, юридическое лицо, тип карты и согласование.</p></div></div>
            <div className="iiko-fields">
              <label className="iiko-wide">Локация<input value="Шерегеш" readOnly /><small>Сейчас оформление доступно только для Шерегеша.</small></label>
              {reference.fields.map((field) => <label key={field.key}>
                {field.label} <span aria-hidden="true">*</span>
                <select required value={draft[field.key]} onChange={(event) => update(field.key, event.target.value)}>
                  <option value="">Выберите значение</option>
                  {optionsFor(field.key).map(option => <option key={option.id} value={option.id}>{option.name}</option>)}
                </select>
              </label>)}
            </div>
            <div className="iiko-category-note"><h3>Эталон заполнения</h3><p>Начальные значения заполнены по тестовой карте. Списки загружаются из базы AYS Connect и связаны с категориями iiko.</p></div>
            {review && <div className="iiko-review" role="status">
              <CheckCircle2 size={20} /><div><h3>Данные подготовлены к проверке</h3>
                <p>{[draft.surname, draft.name, draft.patronymic].filter(Boolean).join(" ")}</p>
                <p>Карта {draft.cardNumber.trim()} · Шерегеш · пополнение {draft.topupAmount} ₽ · AYS Sheregesh</p>
                <p className="iiko-comment"><b>Комментарий:</b> {draft.comment || "Не указан"}</p>
                <dl className="iiko-review-categories">{reference.fields.map((field) => <div key={field.key}>
                  <dt>{field.label}</dt><dd>{optionsFor(field.key).find(option => option.id === draft[field.key])?.name || "Не выбрано"}</dd>
                </div>)}</dl>
                <p>Будет создан новый гость с картой и назначены выбранные категории. После проверки карты будет выполнено указанное пополнение кошелька AYS Sheregesh.</p>
              </div>
            </div>}
            </fieldset>
            {preparing && <p className="iiko-feedback" role="status">Проверяем регистрацию и возможные совпадения ФИО…</p>}
            {review && preparation && !creation && <>
              <p className="iiko-feedback">{preparation.coverage}</p>
              {requiresDuplicateConfirmation && <section className="iiko-confirmation" aria-label="Совпадения ФИО">
                <h3>Возможно, такой гость уже есть</h3>
                <p>Совпадают имя и фамилия. Отчество может отличаться или отсутствовать. Это предупреждение, а не запрет для однофамильцев.</p>
                {preparation.duplicates.map(guest => <React.Fragment key={guest.customerId}>{guestDetails(guest)}</React.Fragment>)}
                {(preparation.incomplete || preparation.limited) && <p>Не все совпадения удалось проверить. Уточните данные перед продолжением.</p>}
                <label className="iiko-confirm-check"><input type="checkbox" checked={confirmDuplicates} disabled={creating} onChange={event => setConfirmDuplicates(event.target.checked)} />Я проверил совпадения и подтверждаю создание отдельного гостя.</label>
              </section>}
              {preparation.existingCard && <section className="iiko-confirmation iiko-confirmation-danger" aria-label="Подтверждение передачи карты">
                <h3>Карта {draft.cardNumber} уже зарегистрирована</h3>
                <p>Будет удалён следующий гость iikoCard:</p>
                {guestDetails(preparation.existingCard)}
                <p>Будет удалён прежний гость целиком, включая доступ через все перечисленные карты. Его балансы и история не переносятся новому гостю. Затем карта будет зарегистрирована на {[draft.surname, draft.name, draft.patronymic].filter(Boolean).join(" ")}.</p>
                {preparation.canReplace ? <label className="iiko-confirm-check"><input type="checkbox" checked={confirmReplacement} disabled={creating} onChange={event => setConfirmReplacement(event.target.checked)} />Подтверждаю удаление показанного гостя со всеми его картами и создание нового владельца.</label> : <p>Для передачи карты требуется отдельное право. Обратитесь к администратору.</p>}
              </section>}
            </>}
            {creating && <p className="iiko-feedback" role="status">Операция выполняется. Ожидайте результат…</p>}
            {creationMessage && <p className="iiko-feedback" role="alert">{creationMessage}</p>}
            {creation && <section className="iiko-review" aria-label="Результат создания" role="status"><div>
              <h3>{creation.status === "succeeded" ? "Карта создана и проверена" : creation.status === "failed" ? "Карта не создана" : creation.status === "needs_review" ? "Создание не завершено — нужна проверка" : "Операция ещё не завершена"}</h3>
              <p>{creation.status === "succeeded" ? (creation.topupConfirmed ? "Гость, карта, четыре категории и пополнение кошелька подтверждены в iiko." : "Гость, карта и категории подтверждены. В этой операции пополнение не выполнялось.") : creation.status === "failed" ? ({
                topup_wallet_unavailable: "Кошелёк AYS Sheregesh недоступен или программа отключена. Создание не начиналось.",
                card_occupied: "Номер уже зарегистрирован. Существующий владелец не изменён.",
                reference_unavailable: "Одна из эталонных категорий отсутствует или отключена.",
                unexpected_default_categories: "В iiko включены дополнительные категории для новых гостей. Требуется сверка с регламентом.",
              } as Record<string, string>)[creation.errorCode] || "Предварительная проверка не прошла. Запись в iiko не начиналась. Проверьте подключение и данные." : "Не отправляйте создание повторно. Обновите статус; если он не меняется, передайте номер операции разработчику."}</p>
              <p className="iiko-owner-id">Операция: {creation.operationId}</p>
              {creation.customerId && <p className="iiko-owner-id">ID гостя операции: {creation.customerId}</p>}
              {creation.status !== "succeeded" && <p>Шаг: {({
                preflight: "предварительная проверка", remove_card: "снятие прежней регистрации", delete_customer: "удаление прежнего гостя", verify_removal: "проверка освобождения карты", create_customer: "создание владельца",
                category_legalEntity: "назначение юридического лица", category_department: "назначение подразделения",
                category_cardType: "назначение типа карты", category_approval: "назначение согласования",
                add_card: "привязка карты", verify: "проверка результата", topup_wallet: "пополнение кошелька", verify_topup: "проверка пополнения",
              } as Record<string, string>)[creation.stage] || "уточнение результата"}</p>}
              {creation.topupAmount && <p>Пополнение: {creation.topupAmount} ₽ · {creation.topupConfirmed ? "подтверждено" : "не подтверждено"}</p>}
              {creation.httpStatus && <p>Ответ iiko: HTTP {creation.httpStatus}</p>}
              {creation.errorHint && <p>{creation.errorHint}</p>}
              {creation.updatedAt && <p>Время фиксации: {new Date(creation.updatedAt).toLocaleString("ru-RU")}</p>}
              {creation.diagnostics?.endpoint && <p className="iiko-owner-id">Метод iiko: {creation.diagnostics.endpoint}</p>}
              {Object.entries(creation.diagnostics?.fields || {}).map(([key, value]) => <p className="iiko-comment" key={key}><b>{key}:</b> {value}</p>)}
              {creation.httpStatus && !Object.keys(creation.diagnostics?.fields || {}).length && <p>Подробности ошибки отсутствуют в сохранённом ответе.</p>}
              {creation.correlationId && <p className="iiko-owner-id">Код обращения iiko: {creation.correlationId}</p>}
              <p>Категорий подтверждено: {creation.completedCategories.length} из 4</p>
            </div></section>}
            <div className="iiko-actions">
              <button type="button" className="iiko-secondary" disabled={preparing || creating || Boolean(operationId && (!creation || creation.status === "running"))} onClick={() => {
                setDraft(emptyDraft); setReview(false); setPreparation(null); setCreation(null); setCreationMessage(""); saveOperation(null);
              }}>{creation ? "Новая карта" : "Очистить"}</button>
              {operationId && <button type="button" className="iiko-secondary" disabled={creating} onClick={() => void refreshCreation(operationId)}>Обновить статус</button>}
              {creation?.status === "succeeded" && draft.cardNumber && <button type="button" className="iiko-secondary" onClick={() => {
                clearCheck(); setNumber(draft.cardNumber); setTab("check");
              }}>Перейти к проверке</button>}
              {review ? <button className="iiko-primary" type="button" disabled={creationLocked || confirmationMissing} onClick={() => void create()}><Plus size={17} />{creating ? "Оформляем…" : preparation?.existingCard ? "Удалить гостя и создать нового" : "Создать карту"}</button>
                : <button className="iiko-primary" type="submit" disabled={creationLocked}>Проверить данные<CheckCircle2 size={17} /></button>}
            </div>
          </form>
        </div>

        <div role="tabpanel" id="iiko-panel-check" aria-labelledby="iiko-tab-check" hidden={tab !== "check"}>
          <div className="iiko-form">
            <div className="iiko-section-title"><span><Search size={18} /></span><div><h2>Найти карту</h2><p>Проверьте владельца, категории и баланс по номеру карты.</p></div></div>
            <form autoComplete="off" onSubmit={check} aria-busy={checking}>
              <label className="iiko-search-label">Номер карты <span aria-hidden="true">*</span>
                <div className="iiko-search-row"><input required pattern=".*\S.*" maxLength={256} value={number} onChange={(e) => { setNumber(e.target.value); clearCheck(); }} placeholder="Введите номер карты" spellCheck={false} />
                  <button type="submit" className="iiko-primary" disabled={checking}><Search size={17} />{checking ? "Проверяем…" : "Проверить карту"}</button></div>
              </label>
            </form>
            {message && <p className="iiko-feedback" role="status">{message}</p>}
            {checking && <p className="iiko-feedback" role="status">Получаем сведения из iiko…</p>}
            {result ? <section className="iiko-result" aria-label="Результат проверки">
              <div className="iiko-result-heading" role="status"><CheckCircle2 size={22} /><div><h3>Карта {result.card} найдена</h3><p>Актуальные данные iiko · Шерегеш</p></div></div>
              <h3>Владелец</h3>{result.owner && <p>{[result.owner.surname, result.owner.name, result.owner.patronymic].filter(Boolean).join(" ")}</p>}<p className="iiko-owner-id">ID гостя: {result.customerId}</p>
              <h3>Привязанные карты · {result.cards.length}</h3>
              <ul className="iiko-result-tags">{result.cards.map((card, index) => <li key={card.id || index}>{card.number}</li>)}</ul>
              {!result.cards.length && <p>Привязанных карт в ответе нет.</p>}
              <h3>Данные карты</h3>
              <p className="iiko-comment"><b>Комментарий:</b> {result.comment || "Не указан"}</p>
              <dl className="iiko-card-entities">
                <div><dt>Локация</dt><dd>{result.connectionId === reference.connectionId ? "Шерегеш" : "Не определена"}</dd></div>
                {cardEntities.map(({ key, label, category }) => <div key={key}>
                  <dt>{label}</dt><dd className={!category ? "iiko-entity-missing" : undefined}>
                    {category ? <>{category.name || "Без названия"}{category.isActive === false && <small>Неактивная категория</small>}</> : "Не указано"}
                  </dd>
                </div>)}
              </dl>
              {otherCategories.length > 0 && <>
                <h3>Другие категории · {otherCategories.length}</h3>
                <ul className="iiko-result-tags">{otherCategories.map((category) => <li key={category.id}>{category.name || "Без названия"}{category.isActive === false ? " · неактивна" : ""}</li>)}</ul>
              </>}
              <h3>Кошельки и балансы</h3>
              {result.walletBalances.map((wallet) => <div className="iiko-wallet" key={wallet.id}>
                <div><b>{wallet.name || "Кошелёк"}</b><span>{["Депозит / корпоративное питание", "Бонусный кошелёк", "Продуктовая программа", "Скидочная программа", "Сертификаты"][wallet.type ?? -1] || "Тип не указан"}</span></div>
                <strong>{typeof wallet.balance === "number" ? wallet.balance.toLocaleString("ru-RU", { maximumFractionDigits: 2 }) : "Не указан"}</strong>
              </div>)}
              {!result.walletBalances.length && <p>Кошельки в ответе отсутствуют.</p>}
            </section> : !checking && !message && <div className="iiko-empty"><CreditCard size={38} strokeWidth={1.3} /><h3>Сведения о карте</h3>
              <p>Введите номер карты, чтобы получить владельца, привязанные карты, категории и балансы.</p>
              <div className="iiko-empty-tags"><span>Владелец</span><span>Категории</span><span>Баланс</span></div>
            </div>}
            <section className="iiko-removal" aria-labelledby="iiko-removal-title">
              <div><h3 id="iiko-removal-title">Удаление гостя и переоформление карты</h3><p>Освобождение карты для передачи другому сотруднику. Для передачи заполните форму создания на нового владельца: она покажет прежнего гостя, все его карты и балансы и запросит подтверждение удаления гостя.</p></div>
              <button type="button" disabled={creationLocked} className="iiko-secondary" onClick={() => {
                update("cardNumber", result?.card || number); setTab("create"); clearCheck();
              }}><Trash2 size={17} />Передать карту новому владельцу</button>
            </section>
          </div>
        </div>
      </section>

      <aside className="iiko-side">
        <div className="iiko-card-preview" aria-label="Лимит карты сотрудника">
          <div><span>AYS</span><CreditCard size={26} /></div><p>Карта сотрудника</p><strong>{draft.cardType === reference.fields[2].id ? <>10 000 <small>₽</small></> : "Не задан"}</strong><span>Лимит карты · Шерегеш</span>
        </div>
        <div className="iiko-help" id="iiko-stage-note"><h2>Работа с картой</h2><p>Создание регистрирует нового гостя с картой, назначает четыре категории и пополняет кошелёк AYS Sheregesh. Для занятого номера потребуется подтверждение удаления прежнего гостя.</p><p>Для карты питания сумма по умолчанию 10 000 ₽. Для остальных типов введите сумму. При обрыве связи обновите статус: не отправляйте пополнение повторно.</p></div>
        <a className="iiko-back" href="#dashboard"><ArrowLeft size={16} />На главную</a>
      </aside>
    </div>
  </main>;
}
