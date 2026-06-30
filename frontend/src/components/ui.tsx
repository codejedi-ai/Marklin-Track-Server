import type { ReactNode } from "react";
import type { Priority, Status } from "../types";

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className}`}
      width="18" height="18" viewBox="0 0 24 24" fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity="0.25" />
      <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="4"
            strokeLinecap="round" />
    </svg>
  );
}

export function Chip({
  children, tone = "slate",
}: { children: ReactNode; tone?: "slate" | "brand" }) {
  // Static class strings only (Tailwind purges dynamically-built names).
  const cls =
    tone === "brand"
      ? "bg-brand-100 text-brand-700"
      : "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {children}
    </span>
  );
}

const PRIORITY_TONE: Record<Priority, string> = {
  High: "bg-red-100 text-red-700 ring-red-200",
  Medium: "bg-amber-100 text-amber-700 ring-amber-200",
  Low: "bg-emerald-100 text-emerald-700 ring-emerald-200",
};

export function PriorityBadge({ value }: { value: Priority }) {
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold
      ring-1 ring-inset ${PRIORITY_TONE[value] ?? "bg-slate-100 text-slate-700"}`}>
      {value}
    </span>
  );
}

const STATUS_TONE: Record<Status, string> = {
  New: "bg-blue-100 text-blue-700",
  "In Progress": "bg-violet-100 text-violet-700",
  Resolved: "bg-emerald-100 text-emerald-700",
};

export function StatusBadge({ value }: { value: Status }) {
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold
      ${STATUS_TONE[value] ?? "bg-slate-100 text-slate-700"}`}>
      {value}
    </span>
  );
}

export function Field({
  label, children, hint,
}: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  );
}
