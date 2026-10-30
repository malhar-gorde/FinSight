"use client";

import { Check, Download, RotateCcw, Trash2 } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import useSWR from "swr";
import { useToast } from "@/components/providers";
import { useMeta } from "@/components/shell";
import { Banner, Card, ConfirmAction, ErrorNote, Field, LoadingPage, PageHeader } from "@/components/ui";
import { api, refreshAll } from "@/lib/api";
import type { RecordCounts } from "@/lib/types";

const LABELS = { transactions: "Transactions", budgets: "Budgets", savings_goals: "Savings goals", investments: "Investments" };
const STORAGE = {
  postgres: "PostgreSQL database — records are stored permanently.",
  local: "Local SQLite file (data/finsight.db) on this computer.",
  temporary: "Temporary storage — data resets when the server restarts. Connect a database to keep it.",
};

export default function SettingsPage() {
  const notify = useToast();
  const { data: meta, error } = useMeta();
  const { data: status } = useSWR<RecordCounts>("/data/status");
  const [name, setName] = useState("");
  const [caution, setCaution] = useState(75);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (meta) { setName(meta.user_name); setCaution(meta.caution_threshold); }
  }, [meta]);

  const header = <PageHeader eyebrow="Preferences" title="Settings" subtitle="Personalise FinSight and manage your data." />;
  if (error) return <>{header}<ErrorNote error={error} /></>;
  if (!meta) return <>{header}<LoadingPage /></>;

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.put("/settings", { user_name: name, caution_threshold: caution });
      notify("Preferences saved.");
      await refreshAll();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Couldn't save.", "error");
    } finally {
      setBusy(false);
    }
  }

  const action = (path: string, message: string) => async () => {
    try {
      await api.post(path, { confirm: "DELETE" });
      notify(message);
      await refreshAll();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Action failed.", "error");
    }
  };

  const hasSample = meta.has_sample_data;

  return (
    <>
      {header}
      <div className="grid grid-2-even">
        <div className="stack">
          <Card title="Profile & preferences">
            <form onSubmit={save}>
              <div className="stack" style={{ gap: 14 }}>
                <Field label="Your first name" hint="Used for the greeting on the Overview page.">
                  <input className="input" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} />
                </Field>
                <Field label={`Budget caution threshold: ${caution}%`}
                  hint="A budget shows Caution once spending reaches this share of its limit. Above 100% is always Exceeded.">
                  <input type="range" min={50} max={95} step={5} value={caution} onChange={(e) => setCaution(Number(e.target.value))} />
                </Field>
              </div>
              <div className="form-actions"><button className="btn btn-primary" disabled={busy}><Check size={16} />Save preferences</button></div>
            </form>
          </Card>
          <Card title="Export" subtitle="Download a copy of everything stored in FinSight.">
            <a className="btn" href="/api/py/data/export.zip" download><Download size={16} />Download all data (ZIP of CSV files)</a>
          </Card>
          <Card title="About FinSight">
            <p className="caption" style={{ marginTop: 0 }}>
              Built with Next.js, a Python (FastAPI + pandas) API and PostgreSQL. Investment prices are entered manually; no live
              market data is fetched. Figures are for personal tracking and education only, not financial or investment advice.
            </p>
          </Card>
        </div>

        <Card title="Your data" subtitle={STORAGE[meta.storage_mode]}>
          {meta.storage_mode === "temporary" && <Banner kind="clay">No database is connected, so changes won&apos;t last.</Banner>}
          {status && (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Records</th><th className="r">Your data</th><th className="r">Demo data</th></tr></thead>
              <tbody>{(Object.keys(LABELS) as (keyof typeof LABELS)[]).map((key) => (
                <tr key={key}><td>{LABELS[key]}</td><td className="r">{status.counts[key].user}</td><td className="r">{status.counts[key].sample}</td></tr>
              ))}</tbody>
            </table></div>
          )}
          <p className="caption">Editing a demo record turns it into your own record.</p>

          <div className="stack" style={{ gap: 18, marginTop: 18 }}>
            {hasSample && (
              <div>
                <div className="card-title" style={{ fontSize: "0.92rem" }}>Remove demonstration data</div>
                <p className="caption" style={{ marginBottom: 8 }}>Deletes only records marked Demo. Anything you added or edited is kept.</p>
                <ConfirmAction label="Remove demo data" icon={<Trash2 size={15} />} typed confirmLabel="Confirm"
                  warning="This permanently removes all demo records." onConfirm={action("/data/remove-demo", "Demonstration data removed.")} />
              </div>
            )}
            <div>
              <div className="card-title" style={{ fontSize: "0.92rem" }}>{hasSample ? "Reset" : "Load"} demonstration data</div>
              <p className="caption" style={{ marginBottom: 8 }}>Replaces demo records with a fresh six-month sample dated up to today. Your own records are not touched.</p>
              <ConfirmAction label={`${hasSample ? "Reset" : "Load"} demo data`} icon={<RotateCcw size={15} />} typed confirmLabel="Confirm"
                warning="Existing demo records will be deleted and recreated." onConfirm={action("/data/reset-demo", "Demonstration data loaded.")} />
            </div>
            <div>
              <div className="card-title bad" style={{ fontSize: "0.92rem" }}>Clear all data</div>
              <p className="caption" style={{ marginBottom: 8 }}>Deletes every transaction, budget, goal and investment — including your own. Export first for a backup.</p>
              <ConfirmAction label="Clear all data" icon={<Trash2 size={15} />} typed confirmLabel="Confirm"
                warning="This permanently deletes ALL financial records. It cannot be undone." onConfirm={action("/data/clear", "All records deleted.")} />
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}
