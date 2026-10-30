"use client";

import {
  Area, Bar, CartesianGrid, Cell, ComposedChart, Legend, Line, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis,
  YAxis,
} from "recharts";
import { inr, inrCompact } from "@/lib/format";
import type { BudgetRow, CategoryRow, Goal, Holding, MonthRow } from "@/lib/types";
import { CHART_SEQUENCE, COLORS, statusColor } from "./ui";

const axisTick = { fill: COLORS.stone, fontSize: 12 };

type TipRow = { name?: string | number; value?: number | string; color?: string; payload?: Record<string, unknown> };

function MoneyTooltip({ active, payload, label, percentKeys = [] }: {
  active?: boolean; payload?: TipRow[]; label?: string | number; percentKeys?: string[];
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      {label !== undefined && <div className="t">{label}</div>}
      {payload.map((p) => (
        <div key={String(p.name)} style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="swatch" style={{ background: p.color, margin: 0 }} />
          <span className="muted">{p.name}:</span>
          <b className="num">
            {percentKeys.includes(String(p.name)) ? `${Number(p.value).toFixed(1)}%` : inr(Number(p.value))}
          </b>
        </div>
      ))}
    </div>
  );
}

export function Donut({ data, centerLabel, height = 260 }: {
  data: { name: string; value: number }[]; centerLabel: string; height?: number;
}) {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  return (
    <div style={{ position: "relative", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="66%" outerRadius="96%" paddingAngle={1}
            stroke="#fff" strokeWidth={2} startAngle={90} endAngle={-270} isAnimationActive={false}>
            {data.map((_, i) => <Cell key={i} fill={CHART_SEQUENCE[i % CHART_SEQUENCE.length]} />)}
          </Pie>
          <Tooltip content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0];
            const value = Number(p.value);
            return (
              <div className="chart-tooltip">
                <div className="t">{String(p.name)}</div>
                <div className="num">{inr(value)} · {total ? ((value / total) * 100).toFixed(1) : 0}%</div>
              </div>
            );
          }} />
        </PieChart>
      </ResponsiveContainer>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", pointerEvents: "none" }}>
        <span className="muted" style={{ fontSize: 12 }}>{centerLabel}</span>
        <span className="num" style={{ fontFamily: "var(--font-heading)", fontWeight: 700, fontSize: 20 }}>{inr(total)}</span>
      </div>
    </div>
  );
}

export function Legend2({ rows }: { rows: { name: string; value: number; share: number }[] }) {
  return (
    <div>
      {rows.map((row, i) => (
        <div className="legend-row" key={row.name}>
          <span><span className="swatch" style={{ background: CHART_SEQUENCE[i % CHART_SEQUENCE.length] }} />{row.name}</span>
          <span className="num"><b>{inr(row.value)}</b><span className="muted"> · {row.share.toFixed(0)}%</span></span>
        </div>
      ))}
    </div>
  );
}

export function CategoryDonut({ rows }: { rows: CategoryRow[] }) {
  return <Donut data={rows.map((r) => ({ name: r.category, value: r.amount }))} centerLabel="Total spent" />;
}

export function IncomeExpenseChart({ rows, height = 300 }: { rows: MonthRow[]; height?: number }) {
  const data = rows.map((r) => ({ label: r.label, Income: r.income, Expenses: r.expenses, "Net savings": r.net }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barGap={4} barCategoryGap="28%">
        <CartesianGrid vertical={false} stroke={COLORS.border} />
        <XAxis dataKey="label" tick={axisTick} axisLine={{ stroke: COLORS.border }} tickLine={false} />
        <YAxis tickFormatter={inrCompact} tick={axisTick} axisLine={false} tickLine={false} width={58} />
        <Tooltip content={<MoneyTooltip />} cursor={{ fill: "rgba(163,184,160,0.12)" }} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, color: COLORS.stone }} />
        <Bar dataKey="Income" fill={COLORS.forest} radius={[4, 4, 0, 0]} />
        <Bar dataKey="Expenses" fill={COLORS.sage} radius={[4, 4, 0, 0]} />
        <Line dataKey="Net savings" stroke={COLORS.gold} strokeWidth={2.5} dot={{ r: 4, fill: COLORS.gold, stroke: "#fff", strokeWidth: 2 }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function SavingsTrendChart({ rows, height = 280 }: { rows: MonthRow[]; height?: number }) {
  const data = rows.map((r) => ({ label: r.label, Cumulative: r.cumulative_net, "Savings rate": r.savings_rate }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={COLORS.border} />
        <XAxis dataKey="label" tick={axisTick} axisLine={{ stroke: COLORS.border }} tickLine={false} />
        <YAxis yAxisId="money" tickFormatter={inrCompact} tick={axisTick} axisLine={false} tickLine={false} width={58} />
        <YAxis yAxisId="rate" orientation="right" tickFormatter={(v) => `${Math.round(v)}%`} tick={axisTick}
          axisLine={false} tickLine={false} width={42} />
        <Tooltip content={<MoneyTooltip percentKeys={["Savings rate"]} />} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, color: COLORS.stone }} />
        <Area yAxisId="money" dataKey="Cumulative" name="Cumulative" type="monotone" stroke={COLORS.forest} strokeWidth={2.5}
          fill="rgba(163,184,160,0.25)" dot={{ r: 3, fill: COLORS.forest }} />
        <Line yAxisId="rate" dataKey="Savings rate" type="monotone" stroke={COLORS.gold} strokeDasharray="4 4"
          strokeWidth={2} dot={{ r: 3, fill: COLORS.gold }} connectNulls={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function HorizontalBars({ data, height, colors, keys }: {
  data: Record<string, string | number>[]; height: number; colors: (string | string[])[]; keys: string[];
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} layout="vertical" margin={{ top: 4, right: 12, left: 4, bottom: 0 }} barGap={-14}>
        <CartesianGrid horizontal={false} stroke={COLORS.border} />
        <XAxis type="number" tickFormatter={inrCompact} tick={axisTick} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="name" tick={axisTick} axisLine={false} tickLine={false} width={130} />
        <Tooltip content={<MoneyTooltip />} cursor={{ fill: "rgba(163,184,160,0.12)" }} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, color: COLORS.stone }} />
        {keys.map((key, k) => {
          const color = colors[k];
          return (
            <Bar key={key} dataKey={key} barSize={14} radius={4} fill={Array.isArray(color) ? COLORS.forest : color}>
              {Array.isArray(color) && data.map((_, i) => <Cell key={i} fill={color[i]} />)}
            </Bar>
          );
        })}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function BudgetChart({ rows }: { rows: BudgetRow[] }) {
  const sorted = [...rows].sort((a, b) => b.budget - a.budget);
  return (
    <HorizontalBars height={Math.max(220, sorted.length * 46 + 60)} keys={["Budget", "Spent"]}
      colors={[COLORS.border, sorted.map((r) => statusColor(r.status))]}
      data={sorted.map((r) => ({ name: r.category, Budget: r.budget, Spent: r.spent }))} />
  );
}

export function GoalChart({ goals }: { goals: Goal[] }) {
  return (
    <HorizontalBars height={Math.max(200, goals.length * 52 + 60)} keys={["Target", "Saved"]}
      colors={[COLORS.border, goals.map((g) => (g.completed ? COLORS.gold : COLORS.forest))]}
      data={goals.map((g) => ({ name: g.name, Target: g.target_amount, Saved: Math.min(g.saved_amount, g.target_amount) }))} />
  );
}

export function HoldingsChart({ holdings }: { holdings: Holding[] }) {
  const sorted = [...holdings].sort((a, b) => b.current - a.current);
  return (
    <ResponsiveContainer width="100%" height={Math.max(260, sorted.length * 44 + 60)}>
      <ComposedChart data={sorted.map((h) => ({ name: h.name, Invested: h.invested, "Current value": h.current }))}
        layout="vertical" margin={{ top: 4, right: 12, left: 4, bottom: 0 }} barGap={2}>
        <CartesianGrid horizontal={false} stroke={COLORS.border} />
        <XAxis type="number" tickFormatter={inrCompact} tick={axisTick} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="name" tick={{ ...axisTick, fontSize: 11 }} axisLine={false} tickLine={false} width={150} />
        <Tooltip content={<MoneyTooltip />} cursor={{ fill: "rgba(163,184,160,0.12)" }} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, color: COLORS.stone }} />
        <Bar dataKey="Invested" fill={COLORS.sage} barSize={10} radius={3} />
        <Bar dataKey="Current value" fill={COLORS.forest} barSize={10} radius={3} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
