"use client";

import { formatDate, inr } from "@/lib/format";
import type { Transaction } from "@/lib/types";
import { Badge, DemoBadge } from "./ui";

export function TransactionsTable({ rows, selectedId, onSelect, showNotes = false }: {
  rows: Transaction[]; selectedId?: number | null; onSelect?: (txn: Transaction) => void; showNotes?: boolean;
}) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Date</th><th>Description</th><th>Category</th><th>Type</th><th>Payment</th>
            {showNotes && <th>Notes</th>}
            <th className="r">Amount</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id}
              className={`${onSelect ? "selectable" : ""} ${selectedId === t.id ? "selected" : ""}`}
              onClick={onSelect ? () => onSelect(t) : undefined}
              tabIndex={onSelect ? 0 : undefined}
              onKeyDown={onSelect ? (e) => { if (e.key === "Enter") onSelect(t); } : undefined}>
              <td className="muted">{formatDate(t.date)}</td>
              <td>{t.description} {t.is_sample ? <DemoBadge /> : null}</td>
              <td>{t.category}</td>
              <td><Badge kind={t.type === "Income" ? "healthy" : "neutral"}>{t.type}</Badge></td>
              <td className="muted">{t.payment_method}</td>
              {showNotes && <td className="muted" style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis" }}>{t.notes}</td>}
              <td className={`r strong ${t.type === "Income" ? "good" : ""}`}>
                {t.type === "Income" ? "+" : "−"}{inr(t.amount, 2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
