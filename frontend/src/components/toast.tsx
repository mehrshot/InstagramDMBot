import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { cx } from "./ui";

type Toast = { id: number; kind: "success" | "error"; text: string };
type ToastApi = { success: (text: string) => void; error: (text: string) => void };

const ToastContext = createContext<ToastApi | null>(null);
let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);

  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = nextId++;
    setItems((list) => [...list.slice(-2), { id, kind, text }]);
    setTimeout(() => setItems((list) => list.filter((t) => t.id !== id)), kind === "error" ? 6000 : 3000);
  }, []);

  const [api] = useState<ToastApi>(() => ({
    success: (text) => push("success", text),
    error: (text) => push("error", text),
  }));

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4">
        {items.map((t) => (
          <div
            key={t.id}
            className={cx(
              "pointer-events-auto flex max-w-md items-start gap-2 rounded-lg px-4 py-3 text-sm text-white shadow-lg",
              t.kind === "success" ? "bg-slate-900" : "bg-red-600",
            )}
          >
            {t.kind === "success" ? <CheckCircle2 className="size-5 shrink-0 text-emerald-400" /> : <XCircle className="size-5 shrink-0" />}
            <span className="user-text">{t.text}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast outside ToastProvider");
  return ctx;
}
