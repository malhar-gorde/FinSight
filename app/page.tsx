"use client";

import { ArrowDownRight, ArrowRight, ArrowUpRight, Clock, Percent, Plus, Wallet } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { CategoryDonut, IncomeExpenseChart, Legend2, SavingsTrendChart } from "@/components/charts";
import { MonthSelect, useMonth } from "@/components/month";
import { DemoBanner, useMeta } from "@/components/shell";
import { TransactionsTable } from "@/components/transactions-table";
import {
  Banner, Card, Delta, Empty, ErrorNote, KV, LoadingPage, Metric, PageHeader, Segmented, StatusBadge,
} from "@/components/ui";
import { inr, monthLabel, pct } from "@/lib/format";
import type { Overview } from "@/lib/types";

const PERIODS = { "3M": 3, "6M": 6, "12M": 12 } as const;
type Period = keyof typeof PERIODS;

function greeting(name?: string) {
  const hour = new Date().getHours();
  const part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  return name ? `${part}, ${name}` : part;
}

export default function OverviewPage() {
  const { month, setMonth, options } = useMonth();
  const [period, setPeriod] = useState<Period>("6M");
  const { data: meta } = useMeta();
  const { data, error, isLoading } = useSWR<Overview>(month ? `/overview?month=${month}&months=${PERIODS[period]}` : null);

  const header = (
    <PageHeader eyebrow={greeting(meta?.user_name)} title="Your Financial Overview"
      subtitle="A clearer picture of your financial life.">
      <MonthSelect value={month} options={options} onChange={setMonth} />
      <Link href="/transactions?add=1" className="btn btn-primary"><Plus size={16} />Add transaction</Link>
    </PageHeader>
  );

  if (error) return <>{header}<ErrorNote error={error} /></>;
  if (isLoading || !data) return <>{header}<LoadingPage /></>;

  if (!data.has_transactions) {
    return (
      <>
        {header}
        <Card>
          <Empty icon={Wallet} title="Welcome to FinSight"
            message="Record your first income or expense to start building your dashboard."
            action={<Link href="/transactions?add=1" className="btn btn-primary"><Plus size={16} />Add your first transaction</Link>} />
        </Card>
      </>
    );
  }

  const { comparison: c, categories, monthly, health, recent } = data;
  const current = c.current;
  const hasPrevious = c.previous !== null;
  const monthsWithData = monthly.filter((m) => m.has_data);
  const top = categories[0];

  return (
    <>
      {header}
      <DemoBanner />

      <div className="metrics">
        <Metric label="Total income" value={inr(current.income)} icon={ArrowUpRight} tone="forest"
          foot={<Delta change={c.income_change} />} />
        <Metric label="Total expenses" value={inr(current.expenses)} icon={ArrowDownRight} tone="gold"
          foot={<Delta change={c.expense_change} higherIsGood={false} />} />
        <Metric label="Net savings" value={inr(current.net)} icon={Wallet} tone={current.net >= 0 ? "sage" : "clay"}
          foot={<>Income − expenses{hasPrevious && c.net_change !== null && (
            <> · <span className={`delta ${c.net_change >= 0 ? "good" : "bad"}`}>{inr(c.net_change, 0, true)}</span> vs last month</>
          )}</>} />
        <Metric label="Savings rate" value={pct(current.savings_rate)} icon={Percent} tone="forest"
          foot={current.savings_rate === null
            ? (current.expenses > 0 ? "No income recorded this month" : "Net savings ÷ income × 100")
            : hasPrevious && c.rate_change !== null ? <Delta change={c.rate_change} unit=" pts" /> : "Net savings ÷ income × 100"} />
      </div>

      {current.count === 0 && (
        <Banner kind="info">No transactions recorded in {monthLabel(data.month)} yet. Totals show ₹0 until you add some.</Banner>
      )}

      <div className="grid grid-2">
        <Card title="Spending by category" subtitle="Share of this month's expenses">
          {categories.length === 0 ? (
            <Empty title="No expenses this month" message="Expenses you record will be broken down here." />
          ) : (
            <div className="grid grid-2-even" style={{ alignItems: "center" }}>
              <CategoryDonut rows={categories} />
              <Legend2 rows={categories.map((r) => ({ name: r.category, value: r.amount, share: r.share }))} />
            </div>
          )}
        </Card>

        <Card title="Financial health summary" subtitle="Calculated indicators for the selected month">
          <KV rows={[
            ["Savings rate", current.savings_rate === null ? "No income yet" : pct(current.savings_rate)],
            ["Highest spending category", top ? `${top.category} · ${inr(top.amount)} (${top.share.toFixed(0)}%)` : "—"],
            ["Budget utilisation", health.budget.utilization === null ? "No budgets set" : (
              <span>{health.budget.utilization.toFixed(0)}% of {inr(health.budget.budget)}{" "}
                <StatusBadge status={health.budget.exceeded ? "Exceeded" : health.budget.caution ? "Caution" : "Healthy"} /></span>
            )],
            ["Spending vs last month", c.expense_change === null ? <span className="muted">Not enough data</span>
              : <Delta change={c.expense_change} suffix="" higherIsGood={false} />],
            ["Savings goals funded", health.goals.percent === null ? "No goals yet"
              : `${health.goals.percent.toFixed(0)}% · ${health.goals.completed} of ${health.goals.count} complete`],
            ["Portfolio return (unrealised)", health.portfolio.return_pct === null ? "No holdings yet" : (
              <span><span className={health.portfolio.pnl >= 0 ? "good" : "bad"}>{pct(health.portfolio.return_pct, 1, true)}</span>{" "}
                on {inr(health.portfolio.invested)}</span>
            )],
          ]} />
          <p className="caption">Budget utilisation = spending in budgeted categories ÷ total budget. Goal funding caps
            each goal at its target. No composite score is used.</p>
        </Card>
      </div>

      <div className="grid grid-2 section">
        <Card title="Income vs expenses" subtitle="Monthly totals with net savings"
          action={<Segmented label="Period" options={Object.keys(PERIODS) as Period[]} value={period} onChange={setPeriod} />}>
          {monthsWithData.length === 0 ? (
            <Empty title="No data for this period" message="Add transactions to see monthly totals." />
          ) : (
            <>
              <IncomeExpenseChart rows={monthly} />
              {monthly.length - monthsWithData.length > 0 && (
                <p className="caption">{monthly.length - monthsWithData.length} month(s) in this period have no records and are shown as zero.</p>
              )}
            </>
          )}
        </Card>
        <Card title="Savings trend" subtitle={`Cumulative net savings over ${PERIODS[period]} months`}>
          {monthsWithData.length < 2 ? (
            <Empty icon={Clock} title="Not enough history yet" message="The savings trend needs at least two months with transactions." />
          ) : (() => {
            const [first, last] = monthsWithData.slice(-2);
            const direction = last.net > first.net ? "improved" : last.net < first.net ? "declined" : "held steady";
            return (
              <>
                <SavingsTrendChart rows={monthly} />
                <p className="caption">Net savings {direction} from {inr(first.net)} in {monthLabel(first.month)} to {inr(last.net)} in {monthLabel(last.month)}.</p>
              </>
            );
          })()}
        </Card>
      </div>

      <div className="section">
        <Card title="Recent transactions" subtitle="Your latest activity across all months"
          action={<Link href="/transactions" className="btn">View all transactions<ArrowRight size={16} /></Link>}>
          <TransactionsTable rows={recent} />
        </Card>
      </div>
    </>
  );
}
