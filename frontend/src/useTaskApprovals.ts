import { useEffect, useRef, useState } from 'react';
import { workRequest, WorkApiError } from './workApi';

export type ApprovalEvent = {id:string;sequence:number;round_number:number;action:string;actor_display:string;text:string;created_at:string};
export type Approval = {id:string;comment:string;approver:string;requester_display:string;approver_display:string;status:string;round_number:number;version:number;source_body:string;history:ApprovalEvent[];available_actions:string[]};

// Approval state belongs to the message, never to the task lifecycle.
export function useTaskApprovals(taskId: string) {
  const [state, setState] = useState<{id:string;items:Approval[];error:string}>({id:taskId,items:[],error:''});
  const refreshRef = useRef<() => Promise<void>>(async () => {});
  useEffect(() => {
    let active = true, stopped = false;
    let pending: Promise<void> | null = null;
    let controller: AbortController | null = null;
    const read = (): Promise<void> => {
      if (!active || stopped) return Promise.resolve();
      if (pending) return pending;
      const request = new AbortController();
      controller = request;
      const timeout = window.setTimeout(() => request.abort(), 15000);
      pending = workRequest<Approval[]>(`/tasks/${taskId}/approvals/`, {signal:request.signal,cache:'no-store'}).then(result => {
        if (!active) return;
        const items = Array.isArray(result) ? result : [];
        setState(old => old.id === taskId && !old.error && JSON.stringify(old.items) === JSON.stringify(items) ? old : {id:taskId,items,error:''});
      }).catch(error => {
        if (!active) return;
        stopped = error instanceof WorkApiError && [401,403,404].includes(error.status);
        setState(old => ({id:taskId,items:stopped || old.id !== taskId ? [] : old.items,
          error:error instanceof WorkApiError && error.status === 403 ? '' : stopped ? 'Согласования недоступны. Обновите страницу для проверки доступа.' : 'Не удалось обновить согласования. Повторим автоматически.'}));
      }).finally(() => { window.clearTimeout(timeout); pending = null; });
      return pending;
    };
    // Wait for a pre-command read before fetching the committed command result.
    const refresh = async () => { if (pending) await pending; await read(); };
    refreshRef.current = refresh;
    const visible = () => { if (document.visibilityState === 'visible') void read(); };
    void read();
    const interval = window.setInterval(visible, 5000);
    window.addEventListener('focus', visible);
    window.addEventListener('online', visible);
    document.addEventListener('visibilitychange', visible);
    return () => {
      active = false; controller?.abort(); window.clearInterval(interval);
      window.removeEventListener('focus', visible);
      window.removeEventListener('online', visible);
      document.removeEventListener('visibilitychange', visible);
      if (refreshRef.current === refresh) refreshRef.current = async () => {};
    };
  }, [taskId]);
  return {items:state.id === taskId ? state.items : [],error:state.id === taskId ? state.error : '',refresh:() => refreshRef.current()};
}
