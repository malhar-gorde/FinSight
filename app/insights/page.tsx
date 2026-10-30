"use client";

import {
  AlertCircle, AlertTriangle, ArrowDownRight, ArrowUpRight, Calendar, CheckCircle2, Clock, Download, Info, Percent, Wallet,
} from "lucide-react";
import { useState } from "react";
import useSWR from "swr";
import { IncomeExpenseChart } from "@/components/charts";
import { MonthSelect, useMonth } from "@/components/month";
import { DemoBanner } from "@/components/shell";
import { Card, Delta, Empty, ErrorNote, KV, LoadingPage, Metric, PageHeader, StatusBadge, Tabs } from "@/components/ui";
import { inr, monthLabel, pct } from "@/lib/format";
import type { Insight, MonthRow, Report } from "@/lib/types";

type Tab = "Insights" | "Monthly report" | "Trends";

const SEVERITY_ICON = {
  alert: { icon: AlertCircle, color: "#A4553F" },
  warning: { icon: AlertTriangle, color: "#8C6D3F" },
  positive: { icon: CheckCircle2, color: "#244A3A" },
  info: { icon: Info, color: "#5E7F6B" },
  needs_data: { icon: Clock, color: "#777970" },
};

function InsightsTab({ month }: { month: string }) {
  const { data, error } = useSWR<Insight[]>(`/insights?month=${month}`);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <LoadingPage />;
  const count = (s: Insight["severity"]) => data.filter((i) => i.severity === s).length;
  return (
    <>
      <p className="caption" style={{ marginTop: 0, marginBottom: 12 }}>
        {data.length} insights for {monthLabel(month)} · {count("alert")} alerts · {count("warning")} warnings · {count("positive")} positive
      </p>
      {data.map((insight, i) => {
        const { icon: Icon, color } = SEVERITY_ICON[insight.severity] ?? SEVERITY_ICON.info;
        return (
          <div key={i} className={`insight insight-${insight.severity}`}>
            <Icon size={20} color={color} style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <div className="insight-kicker">{insight.category}</div>
              <div className="insight-title">{insight.title}</div>
              <div className="insight-msg">{insight.message}</div>
              <div className="insight-rule"><b>How this is calculated:</b> {insight.rule}</div>
            </div>
          </div>
        );
      })}
      <p className="caption">Insights come from transparent, rule-based calculations on your saved records only. Nothing is
        random and no external AI service is used. When there isn&apos;t enough history, FinSight says so instead of guessing.</p>
    </>
  );
}

function ReportTab({ month }: { month: string }) {
  const { data, error } = useSWR<Report>(`/report?month=${month}`);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <LoadingPage />;
  if (!data.has_data) {
    return <Card><Empty icon={Calendar} title={`No transactions in ${monthLabel(month)}`} message="Choose another month or add transactions to generate a report." /></Card>;
  }
  const { comparison: c, categories, budgets, goals, portfolio } = data;
  const cur = c.current;
  const prev = c.previous;
  const change = (a: number, b: number, goodUp = true) =>
    b === 0 ? "—" : <Delta change={((a - b) / Math.abs(b)) * 100} suffix="" higherIsGood={goodUp} />;

  return (
    <>
      <div className="metrics">
        <Metric label="Income" value={inr(cur.income)} icon={ArrowUpRight} foot={<Delta change={c.income_change} />} />
        <Metric label="Expenses" value={inr(cur.expenses)} icon={ArrowDownRight} tone="gold" foot={<Delta change={c.expense_change} higherIsGood={false} />} />
        <Metric label="Net savings" value={inr(cur.net)} icon={Wallet} tone={cur.net >= 0 ? "sage" : "clay"} foot="Income − expenses" />
        <Metric label="Savings rate" value={pct(cur.savings_rate)} icon={Percent} foot="Net savings ÷ income × 100" />
      </div>
      <div className="grid grid-2-even">
        <Card title="Category-wise expenditure">
          {categories.length === 0 ? <p className="caption">No expenses recorded this month.</p> : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Category</th><th className="r">Count</th><th className="r">Amount</th><th className="r">Share</th></tr></thead>
              <tbody>{categories.map((r) => (
                <tr key={r.category}><td>{r.category}</td><td className="r">{r.count}</td><td className="r strong">{inr(r.amount)}</td><td className="r">{r.share.toFixed(1)}%</td></tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>
        <Card title="Comparison with previous month" subtitle={monthLabel(c.previous_month)}>
          {prev === null ? <p className="caption">No transactions in the previous month, so no comparison is shown.</p> : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Metric</th><th className="r">Previous</th><th className="r">This month</th><th className="r">Change</th></tr></thead>
              <tbody>
                <tr><td>Income</td><td className="r">{inr(prev.income)}</td><td className="r strong">{inr(cur.income)}</td><td className="r">{change(cur.income, prev.income)}</td></tr>
                <tr><td>Expenses</td><td className="r">{inr(prev.expenses)}</td><td className="r strong">{inr(cur.expenses)}</td><td className="r">{change(cur.expenses, prev.expenses, false)}</td></tr>
                <tr><td>Net savings</td><td className="r">{inr(prev.net)}</td><td className="r strong">{inr(cur.net)}</td>
                  <td className={`r strong ${cur.net >= prev.net ? "good" : "bad"}`}>{inr(cur.net - prev.net, 0, true)}</td></tr>
                <tr><td>Savings rate</td><td className="r">{pct(prev.savings_rate)}</td><td className="r strong">{pct(cur.savings_rate)}</td>
                  <td className="r">{c.rate_change === null ? "—" : <Delta change={c.rate_change} suffix="" unit=" pts" />}</td></tr>
              </tbody>
            </table></div>
          )}
        </Card>
        <Card title="Budget performance">
          {budgets.length === 0 ? <p className="caption">No budgets were set for this month.</p> : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Category</th><th className="r">Budget</th><th className="r">Spent</th><th className="r">Used</th><th>Status</th></tr></thead>
              <tbody>{budgets.map((b) => (
                <tr key={b.id}><td>{b.category}</td><td className="r">{inr(b.budget)}</td><td className="r strong">{inr(b.spent)}</td>
                  <td className="r">{b.percent_used.toFixed(0)}%</td><td><StatusBadge status={b.status} /></td></tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>
        <Card title="Savings goals & portfolio" subtitle="Current position (not month-specific)">
          {goals.length === 0 && portfolio.holdings === 0 ? <p className="caption">No savings goals or investments recorded yet.</p> : (
            <KV rows={[
              ...goals.map((g) => [g.name, `${inr(g.saved_amount)} of ${inr(g.target_amount)} (${Math.min(g.percent, 999).toFixed(0)}%)`] as [string, string]),
              ...(portfolio.holdings ? [
                ["Portfolio invested", inr(portfolio.invested)],
                ["Portfolio current value", inr(portfolio.current)],
                ["Unrealised return", portfolio.return_pct === null ? "—" : pct(portfolio.return_pct, 1, true)],
              ] as [string, string][] : []),
            ]} />
          )}
        </Card>
      </div>
      <div className="form-actions">
        <a className="btn btn-primary" href={`/api/py/transactions/export.csv?month=${month}`} download>
          <Download size={16} />Export {monthLabel(month)} transactions (CSV)
        </a>
        <span className="caption" style={{ marginTop: 0 }}>PDF export isn&apos;t included in this version; the CSV opens in Excel or Google Sheets.</span>
      </div>
    </>
  );
}

function TrendsTab({ month }: { month: string }) {
  const { data } = useSWR<MonthRow[]>(`/monthly?month=${month}&months=12`);
  if (!data) return <LoadingPage />;
  if (data.filter((m) => m.has_data).length < 2) {
    return <Card><Empty icon={Clock} title="Not enough history" message="Trends need at least two months with transactions." /></Card>;
  }
  return <Card title="12-month income, expenses and net savings"><IncomeExpenseChart rows={data} height={340} /></Card>;
}

export default function InsightsPage() {
  const { month, setMonth, options } = useMonth();
  const [tab, setTab] = useState<Tab>("Insights");
  return (
    <>
      <PageHeader eyebrow="Understand your money" title="Financial Insights"
        subtitle="Patterns, alerts and a monthly report built from your own data.">
        <MonthSelect value={month} options={options} onChange={setMonth} />
      </PageHeader>
      <DemoBanner />
      <Tabs<Tab> tabs={["Insights", "Monthly report", "Trends"]} value={tab} onChange={setTab} />
      {!month ? <LoadingPage /> : tab === "Insights" ? <InsightsTab month={month} />
        : tab === "Monthly report" ? <ReportTab month={month} /> : <TrendsTab month={month} />}
    </>
  );
}
