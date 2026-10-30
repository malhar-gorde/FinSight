"use client";

import { AlertCircle, CheckCircle2 } from "lucide-react";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { SWRConfig } from "swr";
import { fetcher } from "@/lib/api";

// ---------------------------------------------------------------- toasts
type Toast = { id: number; message: string; kind: "success" | "error" };
const ToastContext = createContext<(message: string, kind?: Toast["kind"]) => void>(() => {});

export const useToast = () => useContext(ToastContext);

// ---------------------------------------------------------------- shared month
// The selected month is shared across pages so moving between them stays consistent.
type MonthState = { month: string | null; setMonth: (month: string) => void };
const MonthContext = createContext<MonthState>({ month: null, setMonth: () => {} });
const MONTH_KEY = "finsight.month";

export const useSelectedMonth = () => useContext(MonthContext);

export function Providers({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [month, setMonthState] = useState<string | null>(null);

  useEffect(() => {
    try {
      const saved = window.sessionStorage.getItem(MONTH_KEY);
      if (saved && /^\d{4}-\d{2}$/.test(saved)) setMonthState(saved);
    } catch {
      /* storage unavailable: fall back to the current month */
    }
  }, []);

  const setMonth = useCallback((value: string) => {
    setMonthState(value);
    try { window.sessionStorage.setItem(MONTH_KEY, value); } catch { /* ignore */ }
  }, []);

  const notify = useCallback((message: string, kind: Toast["kind"] = "success") => {
    const id = Date.now() + Math.random();
    setToasts((items) => [...items, { id, message, kind }]);
    setTimeout(() => setToasts((items) => items.filter((t) => t.id !== id)), 3800);
  }, []);

  return (
    <SWRConfig value={{ fetcher, revalidateOnFocus: false, keepPreviousData: true }}>
      <ToastContext.Provider value={notify}>
        <MonthContext.Provider value={{ month, setMonth }}>
          {children}
          <div className="toasts" aria-live="polite">
            {toasts.map((t) => (
              <div key={t.id} className={`toast ${t.kind === "error" ? "toast-error" : ""}`}>
                {t.kind === "error" ? <AlertCircle size={18} color="#A4553F" /> : <CheckCircle2 size={18} color="#244A3A" />}
                {t.message}
              </div>
            ))}
          </div>
        </MonthContext.Provider>
      </ToastContext.Provider>
    </SWRConfig>
  );
}
