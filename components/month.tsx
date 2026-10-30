"use client";

import useSWR from "swr";
import { monthLabel } from "@/lib/format";
import { useSelectedMonth } from "./providers";

/** Selected month (shared across pages) plus the list of months to offer. */
export function useMonth(extra = 0) {
  const { data } = useSWR<{ months: string[]; current: string }>(`/months?extra=${extra}`);
  const { month, setMonth } = useSelectedMonth();
  const options = data?.months ?? [];
  const selected = month && (options.length === 0 || options.includes(month)) ? month : data?.current ?? null;
  return { month: selected, setMonth, options };
}

export function MonthSelect({ value, options, onChange, label = "Month" }: {
  value: string | null; options: string[]; onChange: (month: string) => void; label?: string;
}) {
  return (
    <div className="field" style={{ minWidth: 190 }}>
      <label htmlFor="month-select">{label}</label>
      <select id="month-select" className="select" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        {options.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
      </select>
    </div>
  );
}
