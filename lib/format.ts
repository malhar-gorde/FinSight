// Display formatting: Indian rupees, percentages, dates and months.

const inr0 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", {
  style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2,
});

export const EMPTY = "—";

/** 125000 -> "₹1,25,000"; negatives use a true minus sign. */
export function inr(value: number | null | undefined, decimals: 0 | 2 = 0, showSign = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  const body = (decimals === 2 ? inr2 : inr0).format(Math.abs(value));
  const rounded = decimals === 2 ? Math.round(Math.abs(value) * 100) : Math.round(Math.abs(value));
  if (value < 0 && rounded !== 0) return `−${body}`;
  if (showSign && value > 0 && rounded !== 0) return `+${body}`;
  return body;
}

/** Compact axis labels: ₹12.5K, ₹1.2L, ₹3.4Cr. */
export function inrCompact(value: number): string {
  const sign = value < 0 ? "−" : "";
  const abs = Math.abs(value);
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(1)}Cr`;
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(0)}K`;
  return `${sign}₹${abs.toFixed(0)}`;
}

export function pct(value: number | null | undefined, decimals = 1, showSign = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  const sign = showSign && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`.replace("-", "−");
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
  "October", "November", "December"];

/** "2026-10-05" -> "05 Oct 2026" */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return EMPTY;
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d} ${MONTHS[Number(m) - 1]} ${y}`;
}

/** "2026-10" -> "October 2026" (or "Oct 2026") */
export function monthLabel(month: string, short = false): string {
  const [y, m] = month.split("-");
  return `${(short ? MONTHS : MONTHS_LONG)[Number(m) - 1]} ${y}`;
}

export function todayIso(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

export function quantity(value: number | null | undefined): string {
  if (value === null || value === undefined) return EMPTY;
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 4 }).format(value);
}
