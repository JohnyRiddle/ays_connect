import { useEffect, useRef, useState } from "react";
import { tasksApi, WorkApiError } from "./workApi";

// One request at a time; explicit refresh after sending waits for any older read.
export function useTaskComments(taskId: string) {
  const [state, setState] = useState<{ id: string; items: any[]; error: string }>({ id: taskId, items: [], error: "" });
  const refreshRef = useRef<() => Promise<void>>(async () => {});
  useEffect(() => {
    let active = true, stopped = false;
    let pending: Promise<void> | null = null;
    let controller: AbortController | null = null;
    const read = (): Promise<void> => {
      if (!active || stopped) return Promise.resolve();
      if (pending) return pending;
      controller = new AbortController();
      const timeout = window.setTimeout(() => controller?.abort(), 15000);
      pending = tasksApi.comments(taskId, controller.signal).then(items => {
        if (!active) return;
        setState(old => old.id === taskId && !old.error && JSON.stringify(old.items) === JSON.stringify(items) ? old : { id: taskId, items, error: "" });
      }).catch(error => {
        if (!active) return;
        stopped = error instanceof WorkApiError && [401, 403, 404].includes(error.status);
        setState(old => ({ id: taskId, items: stopped || old.id !== taskId ? [] : old.items,
          error: stopped ? "Переписка недоступна. Обновите страницу для проверки доступа." : "Не удалось обновить переписку. Повторим автоматически." }));
      }).finally(() => { window.clearTimeout(timeout); pending = null; });
      return pending;
    };
    const refresh = async () => { if (pending) await pending; await read(); };
    refreshRef.current = refresh;
    const visible = () => { if (document.visibilityState === "visible") void read(); };
    void read();
    const interval = window.setInterval(visible, 5000);
    window.addEventListener("focus", visible);
    document.addEventListener("visibilitychange", visible);
    return () => {
      active = false; controller?.abort(); window.clearInterval(interval);
      window.removeEventListener("focus", visible);
      document.removeEventListener("visibilitychange", visible);
      if (refreshRef.current === refresh) refreshRef.current = async () => {};
    };
  }, [taskId]);
  return { comments: state.id === taskId ? state.items : [], chatError: state.id === taskId ? state.error : "", refreshComments: () => refreshRef.current() };
}
