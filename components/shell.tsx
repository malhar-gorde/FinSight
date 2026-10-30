"use client";

import {
  Flag, LayoutDashboard, Lightbulb, LogOut, Menu, PieChart, ReceiptText, Settings, TrendingUp, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { Meta } from "@/lib/types";
import { Badge, Banner } from "./ui";

export const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/transactions", label: "Transactions", icon: ReceiptText },
  { href: "/budgets", label: "Budgets", icon: PieChart },
  { href: "/goals", label: "Savings Goals", icon: Flag },
  { href: "/investments", label: "Investments", icon: TrendingUp },
  { href: "/insights", label: "Financial Insights", icon: Lightbulb },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect width="40" height="40" rx="11" fill="#244A3A" />
      <rect x="10" y="21" width="4.5" height="9" rx="2.25" fill="#A3B8A0" />
      <rect x="17.75" y="15" width="4.5" height="15" rx="2.25" fill="#A3B8A0" />
      <rect x="25.5" y="10" width="4.5" height="20" rx="2.25" fill="#C5A46D" />
    </svg>
  );
}

export function useMeta() {
  return useSWR<Meta>("/meta");
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { data: meta } = useMeta();

  useEffect(() => setOpen(false), [pathname]);

  if (pathname.startsWith("/login")) return <>{children}</>;

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <div className="shell">
      <div className="mobile-bar">
        <div className="brand"><Logo size={28} /><span className="brand-name">FinSight</span></div>
        <button type="button" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={20} /></button>
      </div>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="brand"><Logo /><span className="brand-name">FinSight</span></div>
          {open && (
            <button type="button" className="btn btn-sm" onClick={() => setOpen(false)} aria-label="Close menu">
              <X size={16} />
            </button>
          )}
        </div>
        <div className="brand-tagline">Understand Your Money. Master Your Future.</div>
        <div className="nav-label">Menu</div>
        <nav className="nav">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} className={isActive(href) ? "active" : ""}
              aria-current={isActive(href) ? "page" : undefined}>
              <Icon size={18} strokeWidth={1.8} />{label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot">
          {meta?.has_sample_data && <div style={{ marginBottom: 8 }}><Badge kind="gold">Demo data loaded</Badge><br />Manage it in Settings.</div>}
          {meta?.storage_mode === "temporary" && <div style={{ marginBottom: 8 }}><Badge kind="exceeded">Temporary storage</Badge></div>}
          Educational tracking tool. Not investment advice.
          {meta?.auth_required && (
            <div>
              <button type="button" onClick={async () => { await api.post("/auth/logout"); window.location.href = "/login"; }}>
                <LogOut size={13} style={{ verticalAlign: "-2px", marginRight: 4 }} />Sign out
              </button>
            </div>
          )}
        </div>
      </aside>
      <main className="main">
        <div className="container">
          {meta?.storage_mode === "temporary" && (
            <Banner kind="clay">
              <b>No database connected.</b> Data is stored temporarily and will reset when the server restarts.
              Connect a Postgres database in Vercel (see README) to keep your records.
            </Banner>
          )}
          {children}
        </div>
      </main>
    </div>
  );
}

export function DemoBanner() {
  const { data: meta } = useMeta();
  if (!meta?.has_sample_data) return null;
  return (
    <Banner kind="gold">
      <b>You&apos;re viewing demonstration data.</b> Sample records are marked <Badge kind="gold">Demo</Badge> and
      can be removed in <Link href="/settings" style={{ textDecoration: "underline" }}>Settings</Link> without
      affecting records you add yourself.
    </Banner>
  );
}
