import { useEffect, useState } from "react";

export type ToastKind = "success" | "error" | "info";

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

const TOAST_EVENT = "petcare:toast";
let counter = 0;

export function pushToast(kind: ToastKind, message: string): void {
  window.dispatchEvent(new CustomEvent(TOAST_EVENT, { detail: { kind, message } }));
}

export function ToastHost() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ kind: ToastKind; message: string }>).detail;
      const item = { id: ++counter, kind: detail.kind, message: detail.message };
      setItems((current) => [...current, item]);
      window.setTimeout(() => {
        setItems((current) => current.filter((toast) => toast.id !== item.id));
      }, 4500);
    };
    window.addEventListener(TOAST_EVENT, handler);
    return () => window.removeEventListener(TOAST_EVENT, handler);
  }, []);

  return (
    <div className="pointer-events-none fixed inset-x-0 top-3 z-50 flex flex-col items-center gap-2 px-4">
      {items.map((item) => (
        <div
          key={item.id}
          className={`pointer-events-auto w-full max-w-md rounded-lg px-4 py-3 text-sm shadow-lg ${
            item.kind === "error"
              ? "bg-rose-600 text-white"
              : item.kind === "success"
                ? "bg-brand-600 text-white"
                : "bg-slate-800 text-white"
          }`}
          role="status"
        >
          {item.message}
        </div>
      ))}
    </div>
  );
}
