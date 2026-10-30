"use client";

import { Check } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api, refreshAll } from "@/lib/api";
import { inr, todayIso } from "@/lib/format";
import type { Meta, Transaction, TxnType } from "@/lib/types";
import { useToast } from "./providers";
import { Field, Segmented } from "./ui";

/** Add a new transaction, or edit an existing one in place when `existing` is given. */
export function TransactionForm({ meta, existing, onDone }: {
  meta: Meta; existing?: Transaction; onDone?: () => void;
}) {
  const notify = useToast();
  const [type, setType] = useState<TxnType>(existing?.type ?? "Expense");
  const [form, setForm] = useState({
    description: existing?.description ?? "",
    category: existing?.category ?? meta.categories[existing?.type ?? "Expense"][0],
    date: existing?.date ?? todayIso(),
    amount: existing ? String(existing.amount) : "",
    payment_method: existing?.payment_method ?? meta.payment_methods[0],
    notes: existing?.notes ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const categories = meta.categories[type];
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  function changeType(next: TxnType) {
    setType(next);
    setForm((f) => ({ ...f, category: meta.categories[next].includes(f.category) ? f.category : meta.categories[next][0] }));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const amount = Number(form.amount);
    if (!form.description.trim()) return setError("Description is required.");
    if (!form.amount || !Number.isFinite(amount) || amount <= 0) return setError("Amount must be greater than zero.");
    setBusy(true);
    try {
      const body = { ...form, type, amount };
      if (existing) {
        await api.put(`/transactions/${existing.id}`, body);
        notify(`Transaction #${existing.id} updated.`);
      } else {
        await api.post("/transactions", body);
        notify(`${type} of ${inr(amount, 2)} saved.`);
        setForm((f) => ({ ...f, description: "", amount: "", notes: "" }));
      }
      await refreshAll();
      onDone?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the transaction.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <div style={{ marginBottom: 14 }}>
        <Segmented label="Transaction type" options={meta.transaction_types} value={type} onChange={changeType} />
      </div>
      <div className="form-grid">
        <Field label="Description">
          <input className="input" value={form.description} onChange={set("description")} maxLength={120}
            placeholder="e.g. Groceries at local store" required />
        </Field>
        <Field label="Amount (₹)" hint="Enter a positive amount; the type decides income or expense.">
          <input className="input num" type="number" inputMode="decimal" min="0" step="0.01" value={form.amount}
            onChange={set("amount")} placeholder="0.00" required />
        </Field>
        <Field label="Category">
          <select className="select" value={form.category} onChange={set("category")}>
            {categories.map((c) => <option key={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Payment method">
          <select className="select" value={form.payment_method} onChange={set("payment_method")}>
            {meta.payment_methods.map((m) => <option key={m}>{m}</option>)}
          </select>
        </Field>
        <Field label="Date">
          <input className="input" type="date" value={form.date} max={todayIso()} onChange={set("date")} required />
        </Field>
        <Field label="Notes (optional)">
          <input className="input" value={form.notes} onChange={set("notes")} maxLength={500} />
        </Field>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="form-actions">
        <button className="btn btn-primary" type="submit" disabled={busy}>
          <Check size={16} />{busy ? "Saving…" : existing ? "Save changes" : "Save transaction"}
        </button>
        {onDone && existing && <button className="btn" type="button" onClick={onDone}>Cancel</button>}
      </div>
    </form>
  );
}
