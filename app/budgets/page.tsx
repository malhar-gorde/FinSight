"use client";

import { AlertTriangle, ArrowDownRight, Check, Copy, Plus, Target, Trash2, Wallet } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import useSWR from "swr";
import { BudgetChart } from "@/components/charts";
import { MonthSelect, useMonth } from "@/components/month";
import { useToast } from "@/components/providers";
import { DemoBanner, useMeta } from "@/components/shell";
import {
  Banner, Card, ConfirmAction, Empty, ErrorNote, Field, LoadingPage, Metric, PageHeader, Progress, StatusBadge,
  statusColor,
} from "@/components/ui";
import { api, refreshAll } from "@/lib/api";
import { inr, monthLabel } from "@/lib/format";
import type { BudgetRow, BudgetsResponse } from "@/lib/types";

function BudgetCard({ row }: { row: BudgetRow }) {
  return (
    <div className="metric">
      <div className="metric-head">
        <span className="card-title">{row.category}</span>
        <StatusBadge status={row.status} />
      </div>
      <div className="metric-value" style={{ fontSize: "1.35rem" }}>
        {inr(row.spent)} <small>of {inr(row.budget)}</small>
      </div>
      <Progress value={row.percent_used} color={statusColor(row.status)} />
      <div className="metric-foot" style={{ display: "flex", justifyContent: "space-between" }}>
        <span>{row.percent_used.toFixed(0)}% used</span>
        {row.remaining >= 0 ? <span>{inr(row.remaining)} left</span> : <span className="bad">{inr(-row.remaining)} over</span>}
      </div>
    </div>
  );
}

function AddBudget({ month, existing }: { month: string; existing: string[] }) {
  const { data: meta } = useMeta();
  const notify = useToast();
  const available = (meta?.expense_categories ?? []).filter((c) => !existing.includes(c));
  const [category, setCategory] = useState("");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!available.includes(category)) setCategory(available[0] ?? "");
  }, [available, category]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const value = Number(amount);
    if (!amount || !(value > 0)) return setError("Budget limit must be greater than zero.");
    setBusy(true);
    try {
      await api.post("/budgets", { month, category, amount: value });
      notify(`${category} budget of ${inr(value)} created for ${monthLabel(month)}.`);
      setAmount("");
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the budget.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Create a budget" subtitle={`Set a spending limit for a category in ${monthLabel(month)}.`}>
      {available.length === 0 ? (
        <p className="caption">Every expense category already has a budget this month. Edit one below instead.</p>
      ) : (
        <form onSubmit={submit} noValidate>
          <div className="form-grid">
            <Field label="Category">
              <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
                {available.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Monthly limit (₹)">
              <input className="input num" type="number" min="0" step="100" value={amount}
                onChange={(e) => setAmount(e.target.value)} placeholder="e.g. 5000" />
            </Field>
          </div>
          {error && <div className="form-error" role="alert">{error}</div>}
          <div className="form-actions">
            <button className="btn btn-primary" type="submit" disabled={busy}><Plus size={16} />Create budget</button>
          </div>
        </form>
      )}
    </Card>
  );
}

function ManageBudget({ month, rows }: { month: string; rows: BudgetRow[] }) {
  const notify = useToast();
  const [id, setId] = useState<number>(rows[0]?.id);
  const row = rows.find((r) => r.id === id) ?? rows[0];
  const [amount, setAmount] = useState(String(row?.budget ?? ""));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setAmount(String(row?.budget ?? "")); setError(null); }, [row?.id, row?.budget]);
  if (!row) return null;

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const value = Number(amount);
    if (!(value > 0)) return setError("Budget limit must be greater than zero.");
    try {
      await api.put(`/budgets/${row.id}`, { amount: value });
      notify(`${row.category} budget updated to ${inr(value)}.`);
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update the budget.");
    }
  }

  return (
    <Card title="Edit or delete a budget">
      <form onSubmit={save} noValidate>
        <div className="form-grid">
          <Field label="Budget">
            <select className="select" value={row.id} onChange={(e) => setId(Number(e.target.value))}>
              {rows.map((r) => <option key={r.id} value={r.id}>{r.category} · {inr(r.budget)}</option>)}
            </select>
          </Field>
          <Field label="New monthly limit (₹)">
            <input className="input num" type="number" min="0" step="100" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </Field>
        </div>
        {error && <div className="form-error" role="alert">{error}</div>}
        <div className="form-actions">
          <button className="btn btn-primary" type="submit"><Check size={16} />Update limit</button>
        </div>
      </form>
      <div style={{ marginTop: 12 }}>
        <ConfirmAction key={row.id} label="Delete budget" icon={<Trash2 size={15} />}
          warning={`Delete the ${row.category} budget for ${monthLabel(month)}? Your transactions are not affected.`}
          onConfirm={async () => {
            await api.del(`/budgets/${row.id}`);
            notify(`${row.category} budget deleted.`);
            await refreshAll();
          }} />
      </div>
    </Card>
  );
}

export default function BudgetsPage() {
  const { month, setMonth, options } = useMonth(2);
  const notify = useToast();
  const { data, error } = useSWR<BudgetsResponse>(month ? `/budgets?month=${month}` : null);

  const header = (
    <PageHeader eyebrow="Plan your month" title="Budgets" subtitle="Set monthly limits and see how your spending measures up.">
      <MonthSelect value={month} options={options} onChange={setMonth} />
    </PageHeader>
  );
  if (error) return <>{header}<ErrorNote error={error} /></>;
  if (!data || !month) return <>{header}<LoadingPage /></>;

  const { items, totals, caution_threshold: caution } = data;

  if (items.length === 0) {
    return (
      <>
        {header}
        <DemoBanner />
        <div className="grid grid-2">
          <Card>
            <Empty icon={Target} title={`No budgets for ${monthLabel(month)}`}
              message="Create a budget to start tracking spending against a limit."
              action={data.previous_count > 0 ? (
                <button type="button" className="btn" onClick={async () => {
                  const result = await api.post<{ copied: number }>("/budgets/copy", { from_month: data.previous_month, to_month: month });
                  notify(`Copied ${result.copied} budgets into ${monthLabel(month)}.`);
                  await refreshAll();
                }}><Copy size={15} />Copy {data.previous_count} budgets from {monthLabel(data.previous_month, true)}</button>
              ) : undefined} />
          </Card>
          <AddBudget month={month} existing={[]} />
        </div>
      </>
    );
  }

  return (
    <>
      {header}
      <DemoBanner />
      <div className="metrics">
        <Metric label="Total budgeted" value={inr(totals.budget)} icon={Target} foot={`${items.length} categories`} />
        <Metric label="Spent in these categories" value={inr(totals.spent)} icon={ArrowDownRight} tone="gold"
          foot={totals.utilization !== null ? `${totals.utilization.toFixed(0)}% of total budget` : ""} />
        <Metric label="Remaining" value={inr(totals.remaining)} icon={Wallet} tone={totals.remaining >= 0 ? "sage" : "clay"}
          foot={totals.remaining >= 0 ? "Across all budgets" : "Over budget overall"} />
        <Metric label="Needs attention" value={totals.exceeded + totals.caution} icon={AlertTriangle}
          tone={totals.exceeded ? "clay" : "gold"} foot={`${totals.exceeded} exceeded · ${totals.caution} at caution`} />
      </div>
      <p className="caption" style={{ marginTop: -6, marginBottom: 14 }}>
        Status: Healthy below {caution}% · Caution from {caution}% to 100% · Exceeded above 100%. Change the caution threshold
        in Settings. Spending comes from expense transactions dated in {monthLabel(month)}.
      </p>

      <div className="metrics">{items.map((row) => <BudgetCard key={row.id} row={row} />)}</div>

      <div className="grid grid-2">
        <div className="stack">
          <Card title="Budget vs actual" subtitle="Spent bars coloured by status"><BudgetChart rows={items} /></Card>
          {data.unbudgeted.length > 0 && (
            <Banner kind="info">
              <b>Spending without a budget:</b>{" "}
              {data.unbudgeted.map((u) => `${u.category} (${inr(u.amount)})`).join(", ")}.
            </Banner>
          )}
        </div>
        <div className="stack">
          <AddBudget month={month} existing={items.map((r) => r.category)} />
          <ManageBudget month={month} rows={items} />
        </div>
      </div>
    </>
  );
}
