import React, { useEffect, useRef, useState } from "react";
import { MessageSquare, X } from "lucide-react";
import { workRequest, WorkApiError } from "./workApi";
import "./feedback.css";

type Entry = { id: string; kind: string; text: string; author_name: string; created_at: string; delivery_status: string };
const labels: Record<string, string> = { pending: "Ожидает Telegram", sending: "Отправляется в Telegram", delivered: "Доставлено в Telegram", unknown: "Результат Telegram неизвестен — нужна проверка", failed: "Telegram: нужна проверка настройки" };

export function FeedbackButton() {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const sending = useRef(false);
  const [kind, setKind] = useState("improvement");
  const [text, setText] = useState("");
  const [command, setCommand] = useState(() => crypto.randomUUID());
  const [attempted, setAttempted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [owner, setOwner] = useState(false);
  const [history, setHistory] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  async function retryDelivery(item: Entry) {
    if (!window.confirm("Проверьте личный Telegram. Сообщение точно не получено? Повтор при неизвестном результате может создать дубль.")) return;
    setBusy(true); setError("");
    try {
      await workRequest(`/feedback/${item.id}/retry/`, { method: "POST", body: JSON.stringify({ confirmed_not_received: true }) });
      setEntries(items => items.map(entry => entry.id === item.id ? { ...entry, delivery_status: "pending" } : entry));
    } catch { setError("Не удалось поставить доставку на повтор. Обновите историю и проверьте статус."); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    let alive = true;
    workRequest<{ can_read: boolean }>("/feedback/capabilities/").then(r => { if (alive) setOwner(r.can_read); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    if (!history) return;
    let alive = true;
    setHistoryBusy(true); setError(""); setEntries([]);
    workRequest<{ results: Entry[]; next: string | null }>(`/feedback/?page=${page}`).then(r => {
      if (alive) { setEntries(r.results); setHasNext(Boolean(r.next)); }
    }).catch(() => { if (alive) setError("Не удалось загрузить обращения. Закройте историю и попробуйте снова."); })
      .finally(() => { if (alive) setHistoryBusy(false); });
    return () => { alive = false; };
  }, [history, page]);

  function close() { dialog.current?.close(); trigger.current?.focus(); }
  function reset() { setText(""); setKind("improvement"); setCommand(crypto.randomUUID()); setAttempted(false); setSaved(false); setError(""); }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (sending.current || !text.trim()) { if (!text.trim()) setError("Введите текст обращения."); return; }
    sending.current = true; setBusy(true); setError(""); setAttempted(true);
    try {
      await workRequest("/feedback/submit/", { method: "POST", body: JSON.stringify({ kind, text: text.trim(), command_id: command }) });
      setSaved(true);
    } catch (e) {
      if (!attempted && e instanceof WorkApiError && ["validation", "throttled"].includes(e.kind)) setAttempted(false);
      setError(e instanceof WorkApiError && ["validation", "throttled", "unauthenticated"].includes(e.kind)
        ? e.message : "Не удалось подтвердить сохранение. Повторите отправку: то же обращение не будет сохранено дважды.");
    } finally { sending.current = false; setBusy(false); }
  }

  return <>
    <button ref={trigger} className="feedback-trigger" aria-label="Обратная связь" title="Обратная связь" onClick={() => { setHistory(false); if (saved) reset(); dialog.current?.showModal(); }}>
      <MessageSquare size={19}/><span>Обратная связь</span>
    </button>
    <dialog className="feedback-dialog" ref={dialog} aria-labelledby="feedback-title" onCancel={e => { e.preventDefault(); close(); }}>
      <div className="feedback-heading"><h2 id="feedback-title">{history ? "Обращения Ивану" : "Обратная связь"}</h2><button type="button" aria-label="Закрыть обратную связь" onClick={close}><X size={20}/></button></div>
      {history ? <>
        <p>Закрытая история. Доступна только Ивану.</p>
        <button type="button" onClick={() => { setHistory(false); setError(""); }}>Написать обращение</button>
        {historyBusy && <p role="status">Загрузка…</p>}
        {error && <p role="alert">{error}</p>}
        {!historyBusy && !error && entries.length === 0 && <p>Обращений пока нет.</p>}
        <div className="feedback-entries">{entries.map(item => <article key={item.id}>
          <strong>{item.kind === "bug" ? "Сообщить об ошибке" : "Предложить улучшение"}</strong>
          <small>{item.author_name} · {new Date(item.created_at).toLocaleString("ru-RU")}</small>
          <p>{item.text}</p><small>{labels[item.delivery_status] || item.delivery_status}</small>
          {["failed", "unknown"].includes(item.delivery_status) && <button disabled={busy} onClick={() => retryDelivery(item)}>Проверил Telegram — повторить доставку</button>}
        </article>)}</div>
        <div className="feedback-actions"><button disabled={busy || historyBusy || page === 1} onClick={() => setPage(p => p - 1)}>Назад</button><span>Страница {page}</span><button disabled={busy || historyBusy || !hasNext} onClick={() => setPage(p => p + 1)}>Далее</button></div>
      </> : saved ? <div role="status"><h3>Обращение сохранено</h3><p>Оно доступно только Ивану. Полный текст поставлен в очередь доставки в его личный Telegram.</p><button onClick={close}>Готово</button></div> : <form onSubmit={submit}>
        <p id="feedback-notice">Обращение направляется Ивану: в закрытую историю и полным текстом в его личный Telegram. Другие сотрудники и администраторы его не увидят.</p>
        <label htmlFor="feedback-kind">Тип обращения</label>
        <select id="feedback-kind" value={kind} disabled={busy || attempted} onChange={e => setKind(e.target.value)}><option value="improvement">Предложить улучшение</option><option value="bug">Сообщить об ошибке</option></select>
        <label htmlFor="feedback-text">Текст обращения</label>
        <textarea id="feedback-text" value={text} maxLength={3000} disabled={busy || attempted} aria-describedby="feedback-notice feedback-help" onChange={e => { setText(e.target.value); setError(""); }} placeholder="Расскажите, что можно улучшить или что не работает"/>
        <small id="feedback-help">{text.length}/3000 · Скриншоты и техническая диагностика не собираются. Не указывайте пароли и другие секреты.</small>
        {error && <p role="alert" className="feedback-error">{error}</p>}
        {attempted && !busy && <p>Текст зафиксирован для безопасного повтора. При закрытии он сохранится до окончания этой сессии страницы.</p>}
        <div className="feedback-actions"><button type="button" onClick={() => { if (!attempted && !busy) reset(); close(); }}>{attempted ? "Закрыть" : "Отмена"}</button><button type="submit" disabled={busy}>{busy ? "Сохраняем…" : attempted ? "Повторить отправку" : "Отправить Ивану"}</button></div>
      </form>}
      {owner && !history && !busy && <button className="feedback-history" type="button" onClick={() => { setPage(1); setHistory(true); }}>Закрытая история обращений</button>}
    </dialog>
  </>;
}
