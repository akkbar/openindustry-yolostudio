import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { ApiError, createClass, deleteClass, listClasses, renameClass, selectClass, type ProjectClasses } from '../api';
import { en } from '../locales/en';

function useClassState(projectId: string) {
  const [data, setData] = useState<ProjectClasses | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(false);
  const active = useRef<AbortController | null>(null);
  const running = useRef(false);
  const refresh = async () => {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setLoading(true); setError(null);
    try {
      const result = await listClasses(projectId, controller.signal);
      if (!controller.signal.aborted && mounted.current) setData(result);
    } catch (failure) {
      if (!controller.signal.aborted && mounted.current) { setData(null); setError(failure instanceof ApiError ? failure.message : en.connectionFailure); }
    } finally { if (!controller.signal.aborted && mounted.current) setLoading(false); }
  };
  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => { mounted.current = false; active.current?.abort(); };
  }, [projectId]);
  const mutate = async (action: () => Promise<unknown>): Promise<boolean> => {
    if (running.current) return false;
    running.current = true; active.current?.abort(); setBusy(true); setError(null);
    try {
      await action();
      // A successful write is not repeated if the follow-up read fails.
      if (mounted.current) await refresh();
      return true;
    } catch (failure) {
      if (mounted.current) setError(failure instanceof ApiError ? failure.message : en.connectionFailure);
      return false;
    } finally { running.current = false; if (mounted.current) { setBusy(false); setLoading(false); } }
  };
  return {
    data, loading, busy, error, refresh,
    selectedClass: data?.classes.find(item => item.id === data.selected_class_id) ?? null,
    add: (name: string) => mutate(() => createClass(projectId, name)),
    rename: (id: string, name: string) => mutate(() => renameClass(projectId, id, name)),
    remove: (id: string) => mutate(() => deleteClass(projectId, id)),
    select: (id: string | null) => mutate(() => selectClass(projectId, id)),
    clearError: () => setError(null),
  };
}

const Context = createContext<ReturnType<typeof useClassState> | null>(null);
export function ProjectClassesProvider({ projectId, children }: { projectId: string; children: ReactNode }) {
  return <Context.Provider value={useClassState(projectId)}>{children}</Context.Provider>;
}
/** Shared by the class manager, image preview, and the future annotation canvas. */
export function useProjectClasses() {
  const context = useContext(Context);
  if (!context) throw new Error(en.classes.contextUnavailable);
  return context;
}
