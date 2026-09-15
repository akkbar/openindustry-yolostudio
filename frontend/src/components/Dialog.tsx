import { useEffect, useRef, type ReactNode } from 'react';

export default function Dialog({ title, busy = false, onClose, children, className = '' }: { title: string; busy?: boolean; onClose: () => void; children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    const previous = document.activeElement as HTMLElement | null;
    dialog.showModal();
    return () => { dialog.close(); if (previous?.isConnected) previous.focus(); };
  }, []);
  return <dialog className={`gallery-dialog ${className}`} ref={ref} aria-label={title} onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <h2>{title}</h2>{children}
  </dialog>;
}
