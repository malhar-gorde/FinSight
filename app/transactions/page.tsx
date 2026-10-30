"use client";

import { ArrowDownRight, ArrowUpRight, ChevronDown, Download, Layers, Plus, Search, Trash2, Wallet, X } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import useSWR from "swr";
import { DemoBanner, useMeta } from "@/components/shell";
import { TransactionForm } from "@/components/transaction-form";
import { TransactionsTable } from "@/components/transactions-table";
import { useToast } from "@/components/providers";
import { Card, ConfirmAction, Empty, ErrorNote, Field, LoadingPage, Metric, PageHeader } from "@/components/ui";
import { api, queryString, refreshAll } from "@/lib/api";
import { inr } from "@/lib/format";
import type { Summary, Transaction, TxnType } from "@/lib/types";

interface ListResponse {
  items: Transaction[];
  summary: Summary;
  total: number;
  bounds: { min: string; max: string } | null;
}

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function TransactionsInner() {
  const params = useSearchParams();
  const notify = useToast();
  const { data: meta } = useMeta();
  const [showAdd, setShowAdd] = useState(params.get("add") === "1");
  const [showFilters, setShowFilters] = useState(false);
  const [search, setSearch] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [types, setTypes] = useState<TxnType[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [methods, setMethods] = useState<string[]>([]);
  const [sort, setSort] = useState("Date (newest first)");
  const [selected, setSelected] = useState<Transaction | null>(null);

  const query = queryString({ search: search.trim(), start, end, types, categories, methods, sort });
  const { data, error, isLoading } = useSWR<ListResponse>(`/transactions${query}`);

  const categoryOptions = useMemo(() => {
    if (!meta) return [];
    return (types.length ? types : meta.transaction_types).flatMap((t) => meta.categories[t]);
  }, [meta, types]);

  const activeFilters = types.length + categories.length + methods.length + (start ? 1 : 0) + (end ? 1 : 0);

  function clearFilters() {
    setSearch(""); setStart(""); setEnd(""); setTypes([]); setCategories([]); setMethods([]);
  }

  const header = (
    <PageHeader eyebrow="Money in & out" title="Transactions" subtitle="Record, search and manage every rupee in and out.">
      <button className="btn btn-primary" type="button" onClick={() => setShowAdd((v) => !v)}>
        {showAdd ? <X size={16} /> : <Plus size={16} />}{showAdd ? "Close form" : "Add transaction"}
      </button>
    </PageHeader>
  );

  if (error) return <>{header}<ErrorNote error={error} /></>;
  if (!meta || (isLoading && !data) || !data) return <>{header}<LoadingPage /></>;

  const selectedFresh = selected ? data.items.find((t) => t.id === selected.id) ?? selected : null;

  return (
    <>
      {header}
      <DemoBanner />

      {(showAdd || data.total === 0) && (
        <Card title="Add a transaction" subtitle="Income increases your totals; expenses reduce them." className="section-gap">
          <TransactionForm meta={meta} />
        </Card>
      )}

      {data.total === 0 ? (
        <div className="section"><Card><Empty title="No transactions yet" message="Use the form above to record your first one." /></Card></div>
      ) : (
        <>
          <div className="section">
            <Card>
              <div className="form-grid form-grid-3" style={{ alignItems: "end" }}>
                <Field label="Search">
                  <div style={{ position: "relative" }}>
                    <Search size={16} style={{ position: "absolute", left: 11, top: 12, color: "#777970" }} />
                    <input className="input" style={{ paddingLeft: 34 }} value={search} onChange={(e) => setSearch(e.target.value)}
                      placeholder="Description, notes or category" />
                  </div>
                </Field>
                <Field label="Sort by">
                  <select className="select" value={sort} onChange={(e) => setSort(e.target.value)}>
                    {meta.sort_options.map((o) => <option key={o}>{o}</option>)}
                  </select>
                </Field>
                <div className="form-actions" style={{ marginTop: 0 }}>
                  <button type="button" className="btn" onClick={() => setShowFilters((v) => !v)} aria-expanded={showFilters}>
                    Filters{activeFilters ? ` (${activeFilters})` : ""}<ChevronDown size={16} />
                  </button>
                  {(activeFilters > 0 || search) && <button type="button" className="btn" onClick={clearFilters}>Clear</button>}
                </div>
              </div>
              {showFilters && (
                <div className="stack" style={{ marginTop: 16, gap: 14 }}>
                  <div className="form-grid">
                    <Field label="From date">
                      <input className="input" type="date" value={start} min={data.bounds?.min} max={end || undefined}
                        onChange={(e) => setStart(e.target.value)} />
                    </Field>
                    <Field label="To date">
                      <input className="input" type="date" value={end} min={start || undefined}
                        onChange={(e) => setEnd(e.target.value)} />
                    </Field>
                  </div>
                  <Field group label="Type">
                    <div className="chips">{meta.transaction_types.map((t) => (
                      <button key={t} type="button" className={`chip ${types.includes(t) ? "on" : ""}`}
                        onClick={() => { setTypes(toggle(types, t)); setCategories([]); }}>{t}</button>
                    ))}</div>
                  </Field>
                  <Field group label="Category">
                    <div className="chips">{categoryOptions.map((c) => (
                      <button key={c} type="button" className={`chip ${categories.includes(c) ? "on" : ""}`}
                        onClick={() => setCategories(toggle(categories, c))}>{c}</button>
                    ))}</div>
                  </Field>
                  <Field group label="Payment method">
                    <div className="chips">{meta.payment_methods.map((m) => (
                      <button key={m} type="button" className={`chip ${methods.includes(m) ? "on" : ""}`}
                        onClick={() => setMethods(toggle(methods, m))}>{m}</button>
                    ))}</div>
                  </Field>
                </div>
              )}
            </Card>
          </div>

          <div className="metrics section">
            <Metric label="Matching transactions" value={data.summary.count.toLocaleString("en-IN")} icon={Layers} tone="sage"
              foot={`of ${data.total.toLocaleString("en-IN")} in total`} />
            <Metric label="Income" value={inr(data.summary.income)} icon={ArrowUpRight} tone="forest" foot="Within the filtered results" />
            <Metric label="Expenses" value={inr(data.summary.expenses)} icon={ArrowDownRight} tone="gold" foot="Within the filtered results" />
            <Metric label="Net" value={inr(data.summary.net)} icon={Wallet} tone={data.summary.net >= 0 ? "sage" : "clay"} foot="Income − expenses" />
          </div>

          {selectedFresh && (
            <div id="edit-panel" style={{ marginBottom: 16, scrollMarginTop: 16 }}>
              <Card title={`Edit transaction #${selectedFresh.id}`} subtitle="Changes update this record in place — no duplicate is created."
                action={<button type="button" className="btn btn-sm" onClick={() => setSelected(null)} aria-label="Close editor"><X size={15} /></button>}>
                <TransactionForm key={selectedFresh.id} meta={meta} existing={selectedFresh} onDone={() => setSelected(null)} />
                <div style={{ marginTop: 14 }}>
                  <ConfirmAction label="Delete transaction" icon={<Trash2 size={15} />}
                    warning={`Delete “${selectedFresh.description}” (${inr(selectedFresh.amount, 2)}) permanently? Dashboard totals update immediately.`}
                    onConfirm={async () => {
                      try {
                        await api.del(`/transactions/${selectedFresh.id}`);
                        notify(`Transaction #${selectedFresh.id} deleted.`);
                        setSelected(null);
                        await refreshAll();
                      } catch (err) {
                        notify(err instanceof Error ? err.message : "Couldn't delete.", "error");
                      }
                    }} />
                </div>
              </Card>
            </div>
          )}

          <Card title="Transaction history" subtitle="Click a row to edit or delete it."
            action={
              <div className="form-actions" style={{ marginTop: 0 }}>
                <a className="btn btn-sm" href={`/api/py/transactions/export.csv${query}`} download><Download size={15} />Export filtered</a>
                <a className="btn btn-sm" href="/api/py/transactions/export.csv" download><Download size={15} />Export all</a>
              </div>
            }>
            {data.items.length === 0 ? (
              <Empty title="No matching transactions" message="Try widening the date range or clearing filters." />
            ) : (
              <TransactionsTable rows={data.items} showNotes selectedId={selectedFresh?.id}
                onSelect={(t) => {
                  setSelected(t);
                  setTimeout(() => document.getElementById("edit-panel")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
                }} />
            )}
          </Card>
        </>
      )}
    </>
  );
}

export default function TransactionsPage() {
  return <Suspense fallback={<LoadingPage />}><TransactionsInner /></Suspense>;
}
