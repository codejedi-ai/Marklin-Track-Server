import type { Status } from "../types";

export interface FilterState {
  category: string;
  status: string;
  tag: string;
}

const STATUSES: Status[] = ["New", "In Progress", "Resolved"];

const selCls =
  "rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm " +
  "focus:border-brand-500 focus:ring-2 focus:ring-brand-100 outline-none";

export function Filters({
  filters, setFilters, categories, tags, count,
}: {
  filters: FilterState;
  setFilters: (f: FilterState) => void;
  categories: string[];
  tags: string[];
  count: number;
}) {
  const active = filters.category || filters.status || filters.tag;
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <select
        className={selCls}
        value={filters.status}
        onChange={(e) => setFilters({ ...filters, status: e.target.value })}
      >
        <option value="">All statuses</option>
        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>

      <select
        className={selCls}
        value={filters.category}
        onChange={(e) => setFilters({ ...filters, category: e.target.value })}
      >
        <option value="">All categories</option>
        {categories.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>

      <select
        className={selCls}
        value={filters.tag}
        onChange={(e) => setFilters({ ...filters, tag: e.target.value })}
      >
        <option value="">All tags</option>
        {tags.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>

      {active && (
        <button
          onClick={() => setFilters({ category: "", status: "", tag: "" })}
          className="text-sm text-slate-500 underline-offset-2 hover:underline"
        >
          Clear
        </button>
      )}

      <span className="ml-auto text-sm text-slate-400">{count} ticket{count === 1 ? "" : "s"}</span>
    </div>
  );
}
