"use client";

import { Check, CheckCircle2, Flag, Percent, PiggyBank, Target, Trash2, Wallet } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import useSWR from "swr";
import { GoalChart } from "@/components/charts";
import { useToast } from "@/components/providers";
import { DemoBanner } from "@/components/shell";
import {
  Badge, COLORS, Card, ConfirmAction, Empty, ErrorNote, Field, KV, LoadingPage, Metric, PageHeader, Progress, Tabs,
} from "@/components/ui";
import { api, refreshAll } from "@/lib/api";
import { formatDate, inr, todayIso } from "@/lib/format";
import type { Contribution, Goal, GoalTotals } from "@/lib/types";

type Tab = "Add contribution" | "Update balance" | "New goal" | "Edit / delete" | "History";

function inDays(days: number) {
  const d = new Date(Date.now() + days * 86400000);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function GoalCard({ goal }: { goal: Goal }) {
  const overdue = !goal.completed && goal.days_left !== null && goal.days_left < 0;
  const rows: [string, ReactNode][] = [
    ["Target date", goal.target_date
      ? `${formatDate(goal.target_date)}${!goal.completed && goal.days_left !== null && goal.days_left >= 0 ? ` · ${goal.days_left} days left` : ""}`
      : "Not set"],
    ["Remaining", inr(goal.remaining)],
  ];
  if (goal.monthly_needed !== null) rows.push(["Needed per month", inr(goal.monthly_needed)]);
  return (
    <div className="metric">
      <div className="metric-head">
        <span className="card-title">{goal.name}</span>
        {goal.completed ? <Badge kind="gold">Completed</Badge> : overdue ? <Badge kind="exceeded">Past target date</Badge>
          : <Badge kind="healthy">In progress</Badge>}
      </div>
      {goal.description && <div className="metric-foot" style={{ marginTop: 4 }}>{goal.description}</div>}
      <div className="metric-value" style={{ fontSize: "1.35rem" }}>{inr(goal.saved_amount)} <small>of {inr(goal.target_amount)}</small></div>
      <Progress value={goal.percent} color={goal.completed ? COLORS.gold : COLORS.forest} />
      <div className="metric-foot"><b>{Math.min(goal.percent, 999).toFixed(0)}%</b> complete</div>
      <KV rows={rows} />
    </div>
  );
}

function GoalPicker({ goals, value, onChange }: { goals: Goal[]; value: number; onChange: (id: number) => void }) {
  return (
    <Field label="Goal">
      <select className="select" value={value} onChange={(e) => onChange(Number(e.target.value))}>
        {goals.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
      </select>
    </Field>
  );
}

function useSubmit() {
  const notify = useToast();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function run(action: () => Promise<string | void>) {
    setError(null);
    setBusy(true);
    try {
      const message = await action();
      if (message) notify(message);
      await refreshAll();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      return false;
    } finally {
      setBusy(false);
    }
  }
  return { error, setError, busy, run };
}

function ContributionForm({ goals }: { goals: Goal[] }) {
  const [id, setId] = useState(goals[0].id);
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(todayIso());
  const [note, setNote] = useState("");
  const { error, setError, busy, run } = useSubmit();
  const goal = goals.find((g) => g.id === id) ?? goals[0];

  async function submit(e: FormEvent) {
    e.preventDefault();
    const value = Number(amount);
    if (!(value > 0)) return setError("Contribution must be greater than zero.");
    const ok = await run(async () => {
      await api.post(`/goals/${goal.id}/contributions`, { amount: value, date, note });
      const completes = goal.saved_amount < goal.target_amount && goal.saved_amount + value >= goal.target_amount;
      return `${inr(value)} added to ${goal.name}.${completes ? " Goal completed!" : ""}`;
    });
    if (ok) { setAmount(""); setNote(""); }
  }

  return (
    <form onSubmit={submit} noValidate>
      <div className="form-grid">
        <GoalPicker goals={goals} value={goal.id} onChange={setId} />
        <Field label="Contribution (₹)">
          <input className="input num" type="number" min="0" step="100" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </Field>
        <Field label="Date"><input className="input" type="date" value={date} max={todayIso()} onChange={(e) => setDate(e.target.value)} /></Field>
        <Field label="Note (optional)"><input className="input" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} /></Field>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="form-actions"><button className="btn btn-primary" disabled={busy}><PiggyBank size={16} />Add contribution</button></div>
    </form>
  );
}

function BalanceForm({ goals }: { goals: Goal[] }) {
  const [id, setId] = useState(goals[0].id);
  const goal = goals.find((g) => g.id === id) ?? goals[0];
  const [amount, setAmount] = useState(String(goal.saved_amount));
  const { error, setError, busy, run } = useSubmit();
  useEffect(() => setAmount(String(goal.saved_amount)), [goal.id, goal.saved_amount]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const value = Number(amount);
    if (amount === "" || !(value >= 0)) return setError("Saved amount cannot be negative.");
    await run(async () => {
      const result = await api.post<{ adjustment: number }>(`/goals/${goal.id}/balance`, { amount: value });
      return result.adjustment ? `${goal.name} balance set to ${inr(value, 2)}.` : "No change — the saved amount is the same.";
    });
  }

  return (
    <form onSubmit={submit} noValidate>
      <div className="form-grid">
        <GoalPicker goals={goals} value={goal.id} onChange={setId} />
        <Field label="New saved amount (₹)">
          <input className="input num" type="number" min="0" step="100" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </Field>
      </div>
      <p className="caption">Currently saved: {inr(goal.saved_amount, 2)}. Setting a new balance records an adjustment for the
        difference, so the history always adds up.</p>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="form-actions"><button className="btn btn-primary" disabled={busy}><Check size={16} />Update saved amount</button></div>
    </form>
  );
}

function GoalForm({ goal, onSaved }: { goal?: Goal; onSaved?: () => void }) {
  const [name, setName] = useState(goal?.name ?? "");
  const [target, setTarget] = useState(goal ? String(goal.target_amount) : "");
  const [saved, setSaved] = useState("");
  const [hasDate, setHasDate] = useState(goal ? Boolean(goal.target_date) : true);
  const [date, setDate] = useState(goal?.target_date ?? inDays(180));
  const [description, setDescription] = useState(goal?.description ?? "");
  const { error, setError, busy, run } = useSubmit();

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("Goal name is required.");
    if (!(Number(target) > 0)) return setError("Target amount must be greater than zero.");
    if (saved && !(Number(saved) >= 0)) return setError("Amount already saved cannot be negative.");
    const body = { name, target_amount: Number(target), target_date: hasDate ? date : null, description,
      initial_saved: Number(saved || 0) };
    const ok = await run(async () => {
      if (goal) {
        await api.put(`/goals/${goal.id}`, body);
        return `Goal “${name.trim()}” updated.`;
      }
      await api.post("/goals", body);
      return `Goal “${name.trim()}” created.`;
    });
    if (ok && !goal) { setName(""); setTarget(""); setSaved(""); setDescription(""); }
    if (ok) onSaved?.();
  }

  return (
    <form onSubmit={submit} noValidate>
      <div className="form-grid">
        <Field label="Goal name"><input className="input" value={name} maxLength={80} placeholder="e.g. Emergency Fund, New Laptop"
          onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Target amount (₹)"><input className="input num" type="number" min="0" step="1000" value={target}
          onChange={(e) => setTarget(e.target.value)} /></Field>
        {!goal && (
          <Field label="Already saved (₹)" hint="Recorded as an opening balance contribution.">
            <input className="input num" type="number" min="0" step="1000" value={saved} onChange={(e) => setSaved(e.target.value)} />
          </Field>
        )}
        <Field group label="Target date">
          <label className="check"><input type="checkbox" checked={hasDate} onChange={(e) => setHasDate(e.target.checked)} />Set a target date</label>
          {hasDate && <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />}
        </Field>
        <Field label="Description (optional)" className="full">
          <input className="input" value={description} maxLength={500} onChange={(e) => setDescription(e.target.value)} />
        </Field>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="form-actions">
        <button className="btn btn-primary" disabled={busy}>{goal ? <Check size={16} /> : <Flag size={16} />}{goal ? "Save changes" : "Create goal"}</button>
      </div>
    </form>
  );
}

function EditGoal({ goals }: { goals: Goal[] }) {
  const notify = useToast();
  const [id, setId] = useState(goals[0].id);
  const goal = goals.find((g) => g.id === id) ?? goals[0];
  return (
    <div className="stack" style={{ gap: 12 }}>
      <GoalPicker goals={goals} value={goal.id} onChange={setId} />
      <GoalForm key={goal.id} goal={goal} />
      <ConfirmAction key={`del-${goal.id}`} label="Delete goal" icon={<Trash2 size={15} />}
        warning={`Delete “${goal.name}” and its ${inr(goal.saved_amount)} contribution history? This cannot be undone.`}
        onConfirm={async () => {
          await api.del(`/goals/${goal.id}`);
          notify(`Goal “${goal.name}” deleted.`);
          await refreshAll();
        }} />
    </div>
  );
}

function History({ goals }: { goals: Goal[] }) {
  const [id, setId] = useState(goals[0].id);
  const goal = goals.find((g) => g.id === id) ?? goals[0];
  const { data } = useSWR<Contribution[]>(`/goals/${goal.id}/contributions`);
  return (
    <div className="stack" style={{ gap: 12 }}>
      <GoalPicker goals={goals} value={goal.id} onChange={setId} />
      {!data ? <p className="caption">Loading…</p> : data.length === 0 ? <p className="caption">No contributions recorded yet.</p> : (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Date</th><th>Type</th><th>Note</th><th className="r">Amount</th></tr></thead>
              <tbody>{data.map((c) => (
                <tr key={c.id}>
                  <td className="muted">{formatDate(c.date)}</td>
                  <td><Badge kind={c.kind === "contribution" ? "healthy" : "neutral"}>{c.kind === "contribution" ? "Contribution" : "Adjustment"}</Badge></td>
                  <td className="muted">{c.note}</td>
                  <td className={`r strong ${c.amount >= 0 ? "good" : "bad"}`}>{inr(c.amount, 2, true)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <p className="caption">Total: {inr(data.reduce((s, c) => s + c.amount, 0), 2)} — matches the saved amount shown for this goal.</p>
        </>
      )}
    </div>
  );
}

export default function GoalsPage() {
  const { data, error } = useSWR<{ items: Goal[]; totals: GoalTotals }>("/goals");
  const [tab, setTab] = useState<Tab>("Add contribution");
  const header = <PageHeader eyebrow="Build your future" title="Savings Goals" subtitle="Give every rupee you save a purpose." />;
  if (error) return <>{header}<ErrorNote error={error} /></>;
  if (!data) return <>{header}<LoadingPage /></>;

  const { items: goals, totals } = data;
  if (goals.length === 0) {
    return (
      <>
        {header}
        <DemoBanner />
        <div className="grid grid-2">
          <Card><Empty icon={Target} title="No savings goals yet" message="Create a goal such as an Emergency Fund or a New Laptop to track your progress." /></Card>
          <Card title="Create your first goal"><GoalForm /></Card>
        </div>
      </>
    );
  }

  return (
    <>
      {header}
      <DemoBanner />
      <div className="metrics">
        <Metric label="Total saved" value={inr(totals.saved)} icon={Wallet} foot={`Across ${totals.count} goals`} />
        <Metric label="Total target" value={inr(totals.target)} icon={Target} tone="sage" foot="Sum of all goal targets" />
        <Metric label="Overall funded" value={totals.percent === null ? "—" : `${totals.percent.toFixed(0)}%`} icon={Percent}
          tone="gold" foot="Each goal capped at its target" />
        <Metric label="Completed" value={`${totals.completed} of ${totals.count}`} icon={CheckCircle2} foot="Goals that reached target" />
      </div>

      <div className="metrics" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
        {goals.map((g) => <GoalCard key={g.id} goal={g} />)}
      </div>

      <div className="grid grid-2-even">
        <div className="stack">
          <Card title="Progress overview" subtitle="Saved amount against each target"><GoalChart goals={goals} /></Card>
          <p className="caption">Goal contributions are tracked separately from income and expense transactions, so adding one
            does not change your monthly totals.</p>
        </div>
        <Card title="Manage goals">
          <Tabs<Tab> tabs={["Add contribution", "Update balance", "New goal", "Edit / delete", "History"]} value={tab} onChange={setTab} />
          {tab === "Add contribution" && <ContributionForm goals={goals} />}
          {tab === "Update balance" && <BalanceForm goals={goals} />}
          {tab === "New goal" && <GoalForm />}
          {tab === "Edit / delete" && <EditGoal goals={goals} />}
          {tab === "History" && <History goals={goals} />}
        </Card>
      </div>
    </>
  );
}
