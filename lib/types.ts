// Shapes returned by the Python API.

export type TxnType = "Income" | "Expense";

export interface Meta {
  transaction_types: TxnType[];
  categories: Record<TxnType, string[]>;
  expense_categories: string[];
  payment_methods: string[];
  investment_categories: string[];
  sort_options: string[];
  user_name: string;
  caution_threshold: number;
  has_sample_data: boolean;
  storage_mode: "postgres" | "temporary" | "local";
  auth_required: boolean;
  today: string;
}

export interface Transaction {
  id: number;
  date: string;
  description: string;
  category: string;
  type: TxnType;
  amount: number;
  payment_method: string;
  notes: string;
  is_sample: number;
}

export interface Summary {
  income: number;
  expenses: number;
  net: number;
  savings_rate: number | null;
  count: number;
}

export interface Comparison {
  month: string;
  previous_month: string;
  current: Summary;
  previous: Summary | null;
  income_change: number | null;
  expense_change: number | null;
  net_change: number | null;
  rate_change: number | null;
}

export interface CategoryRow {
  category: string;
  amount: number;
  share: number;
  count: number;
}

export interface MonthRow {
  month: string;
  label: string;
  income: number;
  expenses: number;
  net: number;
  savings_rate: number | null;
  cumulative_net: number;
  has_data: boolean;
}

export interface BudgetTotals {
  budget: number;
  spent: number;
  remaining: number;
  utilization: number | null;
  exceeded: number;
  caution: number;
}

export interface GoalTotals {
  target: number;
  saved: number;
  percent: number | null;
  completed: number;
  count: number;
}

export interface PortfolioSummary {
  invested: number;
  current: number;
  pnl: number;
  return_pct: number | null;
  holdings: number;
}

export interface Overview {
  month: string;
  has_transactions: boolean;
  comparison: Comparison;
  categories: CategoryRow[];
  monthly: MonthRow[];
  health: { budget: BudgetTotals; goals: GoalTotals; portfolio: PortfolioSummary };
  recent: Transaction[];
}

export type BudgetStatus = "Healthy" | "Caution" | "Exceeded";

export interface BudgetRow {
  id: number;
  category: string;
  budget: number;
  spent: number;
  remaining: number;
  percent_used: number;
  status: BudgetStatus;
}

export interface BudgetsResponse {
  month: string;
  caution_threshold: number;
  items: BudgetRow[];
  totals: BudgetTotals;
  unbudgeted: { category: string; amount: number }[];
  previous_month: string;
  previous_count: number;
}

export interface Goal {
  id: number;
  name: string;
  target_amount: number;
  saved_amount: number;
  target_date: string | null;
  description: string;
  is_sample: number;
  remaining: number;
  percent: number;
  completed: boolean;
  days_left: number | null;
  monthly_needed: number | null;
}

export interface Contribution {
  id: number;
  goal_id: number;
  date: string;
  amount: number;
  kind: "contribution" | "adjustment";
  note: string;
}

export interface Holding {
  id: number;
  name: string;
  category: string;
  valuation_mode: "units" | "fixed";
  quantity: number | null;
  purchase_price: number | null;
  current_price: number | null;
  invested_amount: number | null;
  current_value: number | null;
  purchase_date: string;
  price_updated_at: string;
  notes: string;
  is_sample: number;
  invested: number;
  current: number;
  pnl: number;
  return_pct: number | null;
}

export interface AllocationRow {
  category: string;
  invested: number;
  current: number;
  pnl: number;
  share: number;
}

export interface InvestmentsResponse {
  items: Holding[];
  summary: PortfolioSummary;
  allocation: AllocationRow[];
}

export type Severity = "alert" | "warning" | "positive" | "info" | "needs_data";

export interface Insight {
  category: string;
  severity: Severity;
  title: string;
  message: string;
  rule: string;
}

export interface Report {
  month: string;
  has_data: boolean;
  comparison: Comparison;
  categories: CategoryRow[];
  budgets: BudgetRow[];
  goals: Goal[];
  portfolio: PortfolioSummary;
}

export interface RecordCounts {
  counts: Record<"transactions" | "budgets" | "savings_goals" | "investments", { sample: number; user: number }>;
  storage_mode: Meta["storage_mode"];
}
