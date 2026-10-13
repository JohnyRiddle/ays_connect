import { useEffect, useRef, useState } from "react";
import { Clock3, X } from "lucide-react";

// User-visible release history travels with the frontend artifact it describes.
const patches = [
  { id: "task-patch-pr3", date: "13 октября 2026", title: "Обращения и работа с задачами", changes: [
    "Новые обращения оформляются задачами; отдельный раздел сервисных заявок убран из меню и карточки объекта.",
    "Добавлены ответственное подразделение, пять приоритетов, несколько наблюдателей и упоминания в комментариях.",
    "Задачи проекта наследуют его срок; подключение корпоративного Telegram подготовлено и ожидает настройки сервиса бота.",
  ] },
  { id: "quiet-scrollbar", date: "13 октября 2026", title: "Более аккуратное меню", changes: [
    "Полоса прокрутки меню стала тоньше, с прозрачной дорожкой и приглушённым бегунком в обеих темах.",
  ] },
  { id: "patch-history", date: "13 октября 2026", title: "История обновлений", changes: [
    "Длинный номер сборки заменён компактной кнопкой в меню.",
    "Историю опубликованных изменений можно открыть прямо в приложении.",
  ] },
  { id: "objects-layout", date: "13 октября 2026", title: "Удобный список объектов", changes: [
    "Заголовок и кнопка добавления выровнены в одной строке.",
    "Объекты отображаются компактным списком; дополнительные фильтры раскрываются отдельно.",
    "Для единственной страницы скрыты кнопки пагинации; компоновка адаптирована для телефона.",
  ] },
  { id: "brand-design", date: "13 октября 2026", title: "Фирменный дизайн AYS Connect", changes: [
    "Светлая и тёмная темы с сохранением выбора, фирменная палитра и логотип AYS! CONNECT.",
    "Обновлены навигация, формы, таблицы и оформление разделов.",
    "Карточка задачи стала компактнее: содержание слева, параметры справа, история рядом с комментариями.",
  ] },
];

function HistoryDialog({ version, close }: { version: string; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const scroll = document.body.style.overflow;
    ref.current?.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      ref.current?.close();
      document.body.style.overflow = scroll;
      previous?.focus();
    };
  }, []);
  return <dialog ref={ref} className="release-history" aria-labelledby="release-history-title"
    onCancel={event => { event.preventDefault(); close(); }}
    onClick={event => { if (event.target === event.currentTarget) close(); }}>
    <div className="release-history-content" onClick={event => event.stopPropagation()}>
      <header className="release-history-heading"><div><p>AYS Connect</p><h2 id="release-history-title">История обновлений</h2></div>
        <button type="button" aria-label="Закрыть историю обновлений" onClick={close}><X size={20} /></button>
      </header>
      <p className="release-history-intro">Последние изменения в интерфейсе.</p>
      {patches.map((patch, index) => <article key={patch.id} className="release-entry">
        <div className="release-entry-meta"><time dateTime="2026-10-13">{patch.date}</time>{index === 0 && <span>Последнее обновление</span>}</div>
        <h3>{patch.title}</h3><ul>{patch.changes.map(change => <li key={change}>{change}</li>)}</ul>
      </article>)}
      <details className="release-build"><summary>Сведения о сборке</summary><code>{version}</code></details>
    </div>
  </dialog>;
}

export function ReleaseNotes({ version }: { version: string }) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  useEffect(() => {
    if (!open && wasOpen.current) trigger.current?.focus();
    wasOpen.current = open;
  }, [open]);
  return <>
    <button ref={trigger} type="button" className="release-notes-trigger" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-label="Открыть историю обновлений">
      <Clock3 size={17} /><span>Обновления</span><small>13.10</small>
    </button>
    {open && <HistoryDialog version={version} close={() => setOpen(false)} />}
  </>;
}
