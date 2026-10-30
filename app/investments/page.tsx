"use client";

import { Check, Layers, Percent, Plus, RefreshCw, Trash2, TrendingDown, TrendingUp, Wallet } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import useSWR from "swr";
import { Donut, HoldingsChart, Legend2 } from "@/components/charts";
import { useToast } from "@/components/providers";
import { DemoBanner, useMeta } from "@/components/shell";
import {
  Banner, Card, ConfirmAction, DemoBadge, Empty, ErrorNote, Field, LoadingPage, Metric, PageHeader, Segmented, Tabs,
} from "@/components/ui";
import { api, refreshAll } from "@/lib/api";
import { formatDate, inr, pct, quantity, todayIso } from "@/lib/format";
import type { Holding, InvestmentsResponse, Meta } from "@/lib/types";

type Mode = "Units × price" | "Fixed value";
const MODES: Record<Mode, "units" | "fixed"> = { "Units × price": "units", "Fixed value": "fixed" };
type Tab = "Update valuation" | "Add holding" | "Edit / delete";

function PnL({ pnl, ret }: { pnl: number; ret: number | null }) {
  return <span className={pnl >= 0 ? "good" : "bad"}>{inr(pnl, 0, true)} ({ret === null ? "—" : pct(ret, 1, true)})</span>;
}

function HoldingForm({ meta, holding }: { meta: Meta; holding?: Holding }) {
  const notify = useToast();
  const [mode, setMode] = useState<Mode>(holding?.valuation_mode === "fixed" ? "Fixed value" : "Units × price");
  const str = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v));
  const [f, setF] = useState({
    name: holding?.name ?? "", category: holding?.category ?? meta.investment_categories[0],
    quantity: str(holding?.quantity), purchase_price: str(holding?.purchase_price), current_price: str(holding?.current_price),
    invested_amount: str(holding?.invested_amount), current_value: str(holding?.current_value),
    purchase_date: holding?.purchase_date ?? todayIso(), notes: holding?.notes ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (key: keyof typeof f) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [key]: e.target.value }));
  const num = (v: string) => (v === "" ? null : Number(v));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!f.name.trim()) return setError("Asset name is required.");
    const units = MODES[mode] === "units";
    const body = {
      name: f.name, category: f.category, valuation_mode: MODES[mode], purchase_date: f.purchase_date, notes: f.notes,
      quantity: units ? num(f.quantity) : null, purchase_price: units ? num(f.purchase_price) : null,
      current_price: units ? num(f.current_price) : null,
      invested_amount: units ? null : num(f.invested_amount), current_value: units ? null : num(f.current_value),
    };
    setBusy(true);
    try {
      if (holding) {
        await api.put(`/investments/${holding.id}`, body);
        notify(`${f.name.trim()} updated.`);
      } else {
        await api.post("/investments", body);
        notify(`${f.name.trim()} added to your portfolio.`);
        setF((s) => ({ ...s, name: "", quantity: "", purchase_price: "", current_price: "", invested_amount: "", current_value: "", notes: "" }));
      }
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the holding.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <div style={{ marginBottom: 12 }}>
        <Segmented label="Valuation method" options={Object.keys(MODES) as Mode[]} value={mode} onChange={setMode} />
        <p className="caption">Use units × price for stocks, funds and ETFs; fixed value for assets such as fixed deposits.</p>
      </div>
      <div className="form-grid">
        <Field label="Asset name"><input className="input" value={f.name} maxLength={80} placeholder="e.g. Nifty 50 Index Fund" onChange={set("name")} /></Field>
        <Field label="Asset category">
          <select className="select" value={f.category} onChange={set("category")}>
            {meta.investment_categories.map((c) => <option key={c}>{c}</option>)}
          </select>
        </Field>
        {MODES[mode] === "units" ? (
          <>
            <Field label="Quantity / units"><input className="input num" type="number" min="0" step="any" value={f.quantity} onChange={set("quantity")} /></Field>
            <Field label="Purchase price per unit (₹)"><input className="input num" type="number" min="0" step="any" value={f.purchase_price} onChange={set("purchase_price")} /></Field>
            <Field label="Current price per unit (₹)" hint="Entered manually — FinSight does not fetch market prices.">
              <input className="input num" type="number" min="0" step="any" value={f.current_price} onChange={set("current_price")} />
            </Field>
          </>
        ) : (
          <>
            <Field label="Amount invested (₹)"><input className="input num" type="number" min="0" step="any" value={f.invested_amount} onChange={set("invested_amount")} /></Field>
            <Field label="Current value (₹)" hint="Entered manually, e.g. from your bank statement.">
              <input className="input num" type="number" min="0" step="any" value={f.current_value} onChange={set("current_value")} />
            </Field>
          </>
        )}
        <Field label="Purchase date"><input className="input" type="date" value={f.purchase_date} max={todayIso()} onChange={set("purchase_date")} /></Field>
        <Field label="Notes (optional)" className="full"><input className="input" value={f.notes} maxLength={500} onChange={set("notes")} /></Field>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="form-actions">
        <button className="btn btn-primary" disabled={busy}>{holding ? <Check size={16} /> : <Plus size={16} />}{holding ? "Save changes" : "Add holding"}</button>
      </div>
    </form>
  );
}

function HoldingPicker({ holdings, value, onChange }: { holdings: Holding[]; value: number; onChange: (id: number) => void }) {
  return (
    <Field label="Holding">
      <select className="select" value={value} onChange={(e) => onChange(Number(e.target.value))}>
        {holdings.map((h) => <option key={h.id} value={h.id}>{h.name} ({h.category})</option>)}
      </select>
    </Field>
  );
}

function ValuationForm({ holdings }: { holdings: Holding[] }) {
  const notify = useToast();
  const [id, setId] = useState(holdings[0].id);
  const h = holdings.find((x) => x.id === id) ?? holdings[0];
  const units = h.valuation_mode === "units";
  const currentValue = units ? h.current_price : h.current_value;
  const [value, setValue] = useState(String(currentValue ?? ""));
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setValue(String(currentValue ?? "")), [h.id, currentValue]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (value === "" || !(Number(value) >= 0)) return setError("Enter a valuation of zero or more.");
    try {
      await api.post(`/investments/${h.id}/valuation`, { amount: Number(value) });
      notify(`${h.name} valuation updated.`);
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update the valuation.");
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <div className="form-grid">
        <HoldingPicker holdings={holdings} value={h.id} onChange={setId} />
        <Field label={units ? "New price per unit (₹)" : "New current value (₹)"}>
          <input className="input num" type="number" min="0" step="any" value={value} onChange={(e) => setValue(e.target.value)} />
        </Field>
      </div>
      <p className="caption">Last valued on {formatDate(h.price_updated_at)}. Enter the latest price from your broker or statement.</p>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="form-actions"><button className="btn btn-primary"><RefreshCw size={15} />Update valuation</button></div>
    </form>
  );
}

function EditHolding({ meta, holdings }: { meta: Meta; holdings: Holding[] }) {
  const notify = useToast();
  const [id, setId] = useState(holdings[0].id);
  const h = holdings.find((x) => x.id === id) ?? holdings[0];
  return (
    <div className="stack" style={{ gap: 12 }}>
      <HoldingPicker holdings={holdings} value={h.id} onChange={setId} />
      <HoldingForm key={h.id} meta={meta} holding={h} />
      <ConfirmAction key={`del-${h.id}`} label="Delete holding" icon={<Trash2 size={15} />}
        warning={`Delete ${h.name} from your portfolio? This cannot be undone.`}
        onConfirm={async () => {
          await api.del(`/investments/${h.id}`);
          notify(`${h.name} deleted.`);
          await refreshAll();
        }} />
    </div>
  );
}

export default function InvestmentsPage() {
  const { data: meta } = useMeta();
  const { data, error } = useSWR<InvestmentsResponse>("/investments");
  const [tab, setTab] = useState<Tab>("Update valuation");

  const header = <PageHeader eyebrow="Portfolio" title="Investments" subtitle="Track what you own and how it's performing." />;
  const disclaimer = (
    <Banner kind="info">
      <b>Prices are entered manually.</b> FinSight does not connect to a market-data service, so values are only as current
      as the “Valued on” date. Returns are unrealised and historical, not a guarantee of future performance. This is an
      educational tracking tool, not investment advice.
    </Banner>
  );
  if (error) return <>{header}<ErrorNote error={error} /></>;
  if (!data || !meta) return <>{header}<LoadingPage /></>;

  const { items, summary, allocation } = data;
  if (items.length === 0) {
    return (
      <>
        {header}<DemoBanner />{disclaimer}
        <div className="grid grid-2">
          <Card><Empty icon={TrendingUp} title="No holdings yet" message="Add your first investment to see your portfolio summary." /></Card>
          <Card title="Add a holding"><HoldingForm meta={meta} /></Card>
        </div>
      </>
    );
  }

  return (
    <>
      {header}
      <DemoBanner />
      {disclaimer}
      <div className="metrics">
        <Metric label="Total invested" value={inr(summary.invested)} icon={Wallet} tone="sage" foot={`${summary.holdings} holdings`} />
        <Metric label="Current value" value={inr(summary.current)} icon={Layers} foot="Based on your entered prices" />
        <Metric label="Unrealised profit / loss" value={inr(summary.pnl, 0, true)} icon={summary.pnl >= 0 ? TrendingUp : TrendingDown}
          tone={summary.pnl >= 0 ? "forest" : "clay"} foot="Current value − invested" />
        <Metric label="Return" value={summary.return_pct === null ? "—" : pct(summary.return_pct, 1, true)} icon={Percent} tone="gold"
          foot="P&L ÷ invested × 100" />
      </div>

      <div className="grid grid-2-even">
        <Card title="Allocation by asset class" subtitle="Share of current portfolio value">
          {summary.current <= 0 ? <Empty title="No current value" message="Enter current prices to see your allocation." /> : (
            <>
              <Donut data={allocation.map((a) => ({ name: a.category, value: a.current }))} centerLabel="Current value" />
              <Legend2 rows={allocation.map((a) => ({ name: a.category, value: a.current, share: a.share }))} />
            </>
          )}
        </Card>
        <Card title="Invested vs current value" subtitle="Per holding"><HoldingsChart holdings={items} /></Card>
      </div>

      <div className="section">
        <Card title="Holdings" subtitle="Units-based assets: invested = units × buy price; current = units × current price.">
          <div className="table-wrap">
            <table className="table">
              <thead><tr>
                <th>Asset</th><th>Category</th><th className="r">Units</th><th className="r">Buy price</th><th className="r">Current price</th>
                <th className="r">Invested</th><th className="r">Current value</th><th className="r">Unrealised P&amp;L</th><th>Valued on</th>
              </tr></thead>
              <tbody>{[...items].sort((a, b) => b.current - a.current).map((h) => {
                const units = h.valuation_mode === "units";
                return (
                  <tr key={h.id}>
                    <td>{h.name} {h.is_sample ? <DemoBadge /> : null}</td>
                    <td className="muted">{h.category}</td>
                    <td className="r">{units ? quantity(h.quantity) : "—"}</td>
                    <td className="r">{units ? inr(h.purchase_price, 2) : "—"}</td>
                    <td className="r">{units ? inr(h.current_price, 2) : "—"}</td>
                    <td className="r">{inr(h.invested)}</td>
                    <td className="r strong">{inr(h.current)}</td>
                    <td className="r strong"><PnL pnl={h.pnl} ret={h.return_pct} /></td>
                    <td className="muted">{formatDate(h.price_updated_at)}</td>
                  </tr>
                );
              })}</tbody>
            </table>
          </div>
        </Card>
      </div>

      <div className="section">
        <Card title="Manage portfolio">
          <Tabs<Tab> tabs={["Update valuation", "Add holding", "Edit / delete"]} value={tab} onChange={setTab} />
          {tab === "Update valuation" && <ValuationForm holdings={items} />}
          {tab === "Add holding" && <HoldingForm meta={meta} />}
          {tab === "Edit / delete" && <EditHolding meta={meta} holdings={items} />}
        </Card>
      </div>
    </>
  );
}
