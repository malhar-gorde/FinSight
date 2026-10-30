"use client";

import { AlertTriangle, CheckCircle2, Info, Layers, type LucideIcon } from "lucide-react";
import { type ReactNode, useState } from "react";
import { pct } from "@/lib/format";
import type { BudgetStatus } from "@/lib/types";

export const COLORS = {
  forest: "#244A3A",
  sage: "#A3B8A0",
  gold: "#C5A46D",
  charcoal: "#252923",
  stone: "#777970",
  border: "#E6E3DA",
  clay: "#A4553F",
};

// Balanced across forest, gold and sage so charts never become "all green".
export const CHART_SEQUENCE = ["#244A3A", "#C5A46D", "#A3B8A0", "#5E7F6B", "#8C6D3F", "#D9CBA8", "#3D6553", "#C9D4C5", "#B8B3A6"];

type Tone = "forest" | "sage" | "gold" | "clay";

export function PageHeader({ eyebrow, title, subtitle, children }: {
  eyebrow?: string; title: string; subtitle?: string; children?: ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1 className="title">{title}</h1>
        {subtitle && <p className="subtitle">{subtitle}</p>}
      </div>
      {children && <div className="head-actions">{children}</div>}
    </div>
  );
}

export function Card({ title, subtitle, action, children, className = "" }: {
  title?: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <div className="card-head">
          <div>
            {title && <h2 className="card-title">{title}</h2>}
            {subtitle && <div className="card-sub">{subtitle}</div>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Metric({ label, value, foot, icon: Icon, tone = "forest" }: {
  label: string; value: ReactNode; foot?: ReactNode; icon: LucideIcon; tone?: Tone;
}) {
  return (
    <div className="metric">
      <div className="metric-head">
        <span className="metric-label">{label}</span>
        <span className={`metric-icon tone-${tone}`}><Icon size={16} strokeWidth={1.9} /></span>
      </div>
      <div className="metric-value">{value}</div>
      {foot && <div className="metric-foot">{foot}</div>}
    </div>
  );
}

/** Coloured change indicator, or a neutral note when there is nothing to compare. */
export function Delta({ change, suffix = "vs last month", higherIsGood = true, unit = "%" }: {
  change: number | null | undefined; suffix?: string; higherIsGood?: boolean; unit?: "%" | " pts";
}) {
  if (change === null || change === undefined) return <span className="muted">No previous month to compare</span>;
  if (Math.abs(change) < 0.05) return <span><span className="delta muted">No change</span> {suffix}</span>;
  const good = change > 0 === higherIsGood;
  const text = unit === "%" ? pct(Math.abs(change)) : `${Math.abs(change).toFixed(1)} pts`;
  return (
    <span>
      <span className={`delta ${good ? "good" : "bad"}`}>{change > 0 ? "▲" : "▼"} {text}</span> {suffix}
    </span>
  );
}

export function Badge({ children, kind = "neutral" }: { children: ReactNode; kind?: string }) {
  return <span className={`badge badge-${kind}`}>{children}</span>;
}

export function StatusBadge({ status }: { status: BudgetStatus }) {
  return <Badge kind={status.toLowerCase()}>{status}</Badge>;
}

export function DemoBadge() {
  return <Badge kind="gold">Demo</Badge>;
}

export function statusColor(status: BudgetStatus): string {
  return status === "Exceeded" ? COLORS.clay : status === "Caution" ? COLORS.gold : COLORS.forest;
}

export function Progress({ value, color = COLORS.forest }: { value: number; color?: string }) {
  const width = Math.max(0, Math.min(value || 0, 100));
  return <div className="progress"><div style={{ width: `${width}%`, background: color }} /></div>;
}

export function Banner({ kind = "gold", children }: { kind?: "gold" | "info" | "clay"; children: ReactNode }) {
  const Icon = kind === "clay" ? AlertTriangle : Info;
  return <div className={`banner banner-${kind}`}><Icon size={17} />{<div>{children}</div>}</div>;
}

export function Empty({ title, message, icon: Icon = Layers, action }: {
  title: string; message: string; icon?: LucideIcon; action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon"><Icon size={22} /></div>
      <div className="empty-title">{title}</div>
      <div>{message}</div>
      {action}
    </div>
  );
}

export function Skeleton({ height = 120 }: { height?: number }) {
  return <div className="skeleton" style={{ height }} />;
}

export function LoadingPage() {
  return (
    <div className="stack">
      <Skeleton height={70} />
      <div className="metrics">{[0, 1, 2, 3].map((i) => <Skeleton key={i} height={110} />)}</div>
      <Skeleton height={320} />
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return <Banner kind="clay">Couldn&apos;t load this data: {message}</Banner>;
}

export function KV({ rows }: { rows: [string, ReactNode][] }) {
  return <div>{rows.map(([label, value]) => (
    <div className="kv" key={label}><span className="kv-label">{label}</span><span className="kv-value">{value}</span></div>
  ))}</div>;
}

export function Tabs<T extends string>({ tabs, value, onChange }: {
  tabs: T[]; value: T; onChange: (tab: T) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((tab) => (
        <button key={tab} role="tab" aria-selected={tab === value} className={tab === value ? "on" : ""}
          onClick={() => onChange(tab)} type="button">{tab}</button>
      ))}
    </div>
  );
}

export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: T[]; value: T; onChange: (value: T) => void; label: string;
}) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((option) => (
        <button key={option} type="button" role="radio" aria-checked={option === value}
          className={option === value ? "on" : ""} onClick={() => onChange(option)}>{option}</button>
      ))}
    </div>
  );
}

/**
 * Labelled form control. The <label> wraps the control so it is associated without ids.
 * Use `group` when the children hold several controls (it then renders a fieldset-like div).
 */
export function Field({ label, hint, children, className = "", group = false }: {
  label: string; hint?: string; children: ReactNode; className?: string; group?: boolean;
}) {
  const content = (
    <>
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </>
  );
  return group
    ? <div className={`field ${className}`} role="group" aria-label={label}>{content}</div>
    : <label className={`field ${className}`}>{content}</label>;
}

/**
 * Two-step destructive action: the first click shows a confirmation, the second performs it.
 * When `typed` is set the user must also type DELETE.
 */
export function ConfirmAction({ label, warning, confirmLabel = "Yes, delete", onConfirm, typed = false, icon }: {
  label: string; warning: string; confirmLabel?: string; onConfirm: () => Promise<void>; typed?: boolean;
  icon?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  if (!open) {
    return <button type="button" className="btn btn-danger" onClick={() => setOpen(true)}>{icon}{label}</button>;
  }
  const ready = !typed || text.trim() === "DELETE";
  return (
    <div className="confirm-box">
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
        <AlertTriangle size={17} color={COLORS.clay} style={{ flexShrink: 0, marginTop: 2 }} />
        <span>{warning}</span>
      </div>
      {typed && (
        <label className="field" style={{ marginTop: 10 }}>
          <span className="field-label">Type DELETE to confirm</span>
          <input className="input" value={text} onChange={(e) => setText(e.target.value)} autoComplete="off" />
        </label>
      )}
      <div className="form-actions" style={{ marginTop: 10 }}>
        <button type="button" className="btn btn-danger-solid btn-sm" disabled={!ready || busy}
          onClick={async () => {
            setBusy(true);
            try { await onConfirm(); setOpen(false); setText(""); } finally { setBusy(false); }
          }}>{busy ? "Working…" : confirmLabel}</button>
        <button type="button" className="btn btn-sm" onClick={() => { setOpen(false); setText(""); }}>Cancel</button>
      </div>
    </div>
  );
}

export function SuccessIcon() {
  return <CheckCircle2 size={18} color={COLORS.forest} />;
}
