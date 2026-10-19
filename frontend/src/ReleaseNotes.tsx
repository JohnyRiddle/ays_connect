import { useEffect, useRef, useState } from "react";
import { Clock3, X } from "lucide-react";

// User-visible release history travels with the frontend artifact it describes.
const patches = [
  {
    "id": "updates-2026-10-17",
    "date": "17 октября 2026",
    "dateTime": "2026-10-17",
    "title": "17 октября",
    "changes": [
      "Запросы уточнения теперь отмечены знаком «!» — легче заметить, где нужен ваш ответ.",
      "Ответы на согласование появляются автоматически, без обновления страницы.",
      "Исправлена одна из причин, по которой переписка переставала обновляться.",
      "Если запрос согласования изменился, пока вы готовили ответ, приложение предложит выбрать действие заново. Написанный текст сохранится.",
      "Решение по согласованию не меняет статус самой задачи."
    ]
  },
  {
    "id": "updates-2026-10-16",
    "date": "16 октября 2026",
    "dateTime": "2026-10-16",
    "title": "16 октября",
    "changes": [
      "Новые сообщения в открытом чате появляются автоматически в течение нескольких секунд. Черновик сообщения и место чтения сохраняются.",
      "Свои сообщения показываются справа, сообщения коллег — слева. Добавлены время сообщений и разделители по дням.",
      "Enter отправляет сообщение, Shift+Enter добавляет новую строку.",
      "Запросить согласование можно из заголовка чата, даже если переписка ещё не началась.",
      "Упоминания рядом с колокольчиком помогают перейти сразу в нужную задачу.",
      "Пять последних уведомлений доступны даже после прочтения и обновления страницы. Исправлен счётчик непрочитанных уведомлений.",
      "В карточке сотрудника появились отдельные страницы объектов и доступа с поиском. Одинаковые роли объединены: видно количество назначений.",
      "Чек-листы показаны отдельными карточками, а подпункты меню стали заметнее."
    ]
  },
  {
    "id": "updates-2026-10-15",
    "date": "15 октября 2026",
    "dateTime": "2026-10-15",
    "title": "15 октября",
    "changes": [
      "В задачах доступны согласование, запрос уточнения, повторное согласование и отмена запроса. История ответов сохраняется, согласующего можно выбрать напрямую.",
      "Пункты простого чек-листа можно отмечать галочками — изменения сохраняются сразу. Ранее внесённые ответы сохранены.",
      "Улучшен поиск участников и наблюдателей, а также просмотр изображений.",
      "При выборе приоритета задачи виден её срок."
    ]
  },
  {
    "id": "updates-2026-10-14",
    "date": "14 октября 2026",
    "dateTime": "2026-10-14",
    "title": "14 октября",
    "changes": [
      "Добавлена библиотека шаблонов чек-листов. Шаблоны можно создавать, просматривать, копировать, архивировать и прикреплять к задачам.",
      "Изменение шаблона не затрагивает чек-листы, уже прикреплённые к задачам.",
      "Обязательные пункты чек-листа нужно выполнить перед завершением задачи.",
      "Наблюдателей можно искать по имени и фамилии. Перед удалением приложение попросит подтверждение.",
      "Из аналитики убраны устаревшие показатели сервисных заявок."
    ]
  },
  { id: "task-patch-pr3", date: "13 октября 2026", dateTime: "2026-10-13", title: "Обращения и работа с задачами", changes: [
    "Новые обращения оформляются задачами; отдельный раздел сервисных заявок убран из меню и карточки объекта.",
    "Добавлены ответственное подразделение, пять приоритетов, несколько наблюдателей и упоминания в комментариях.",
    "Задачи проекта наследуют его срок; подключение корпоративного Telegram подготовлено и ожидает настройки сервиса бота.",
  ] },
  { id: "quiet-scrollbar", date: "13 октября 2026", dateTime: "2026-10-13", title: "Более аккуратное меню", changes: [
    "Полоса прокрутки меню стала тоньше, с прозрачной дорожкой и приглушённым бегунком в обеих темах.",
  ] },
  { id: "patch-history", date: "13 октября 2026", dateTime: "2026-10-13", title: "История обновлений", changes: [
    "Длинный номер сборки заменён компактной кнопкой в меню.",
    "Историю опубликованных изменений можно открыть прямо в приложении.",
  ] },
  { id: "objects-layout", date: "13 октября 2026", dateTime: "2026-10-13", title: "Удобный список объектов", changes: [
    "Заголовок и кнопка добавления выровнены в одной строке.",
    "Объекты отображаются компактным списком; дополнительные фильтры раскрываются отдельно.",
    "Для единственной страницы скрыты кнопки пагинации; компоновка адаптирована для телефона.",
  ] },
  { id: "brand-design", date: "13 октября 2026", dateTime: "2026-10-13", title: "Фирменный дизайн AYS Connect", changes: [
    "Светлая и тёмная темы с сохранением выбора, фирменная палитра и логотип AYS! CONNECT.",
    "Обновлены навигация, формы, таблицы и оформление разделов.",
    "Карточка задачи стала компактнее: содержание слева, параметры справа, история рядом с комментариями.",
  ] },
  {
    "id": "updates-2026-10-12",
    "date": "12 октября 2026",
    "dateTime": "2026-10-12",
    "title": "12 октября — дополнение к истории",
    "changes": [
      "Сотрудники могут подать заявку на регистрацию и посмотреть её статус в приложении. Доступ одобряет администратор.",
      "Добавлены приглашения с заданными условиями доступа. Приглашения используются без отправки электронных писем."
    ]
  },
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
        <div className="release-entry-meta"><time dateTime={patch.dateTime}>{patch.date}</time>{index === 0 && <span>Последнее обновление</span>}</div>
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
      <Clock3 size={17} /><span>Обновления</span><small>{patches[0].dateTime.slice(8, 10)}.{patches[0].dateTime.slice(5, 7)}</small>
    </button>
    {open && <HistoryDialog version={version} close={() => setOpen(false)} />}
  </>;
}
