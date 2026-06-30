import { useMemo, useState } from "react";
import type { Status, Ticket } from "../types";
import { TicketCard } from "./TicketCard";
import { Filters, type FilterState } from "./Filters";
import { Spinner } from "./ui";

export function Dashboard({
  tickets, loading, error, busyIds, onReload, onStatusChange,
}: {
  tickets: Ticket[];
  loading: boolean;
  error: string | null;
  busyIds: Set<string>;
  onReload: () => void;
  onStatusChange: (id: string, status: Status) => void;
}) {
  const [filters, setFilters] = useState<FilterState>({ category: "", status: "", tag: "" });

  const categories = useMemo(
    () => [...new Set(tickets.map((t) => t.category).filter(Boolean) as string[])].sort(),
    [tickets]
  );
  const tags = useMemo(
    () => [...new Set(tickets.flatMap((t) => t.tags))].sort(),
    [tickets]
  );

  const filtered = useMemo(
    () => tickets.filter((t) =>
      (!filters.category || t.category === filters.category) &&
      (!filters.status || t.status === filters.status) &&
      (!filters.tag || t.tags.includes(filters.tag))
    ),
    [tickets, filters]
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-slate-400">
        <Spinner /> Loading tickets…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
        <p className="text-sm text-red-700">{error}</p>
        <button onClick={onReload}
                className="mt-3 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Support queue</h2>
        <button onClick={onReload} className="text-sm text-brand-600 hover:text-brand-700">
          ↻ Refresh
        </button>
      </div>

      <Filters filters={filters} setFilters={setFilters}
               categories={categories} tags={tags} count={filtered.length} />

      {tickets.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center text-slate-400">
          No tickets yet. Submit one from the “New ticket” tab.
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center text-slate-400">
          No tickets match these filters.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {filtered.map((t) => (
            <TicketCard key={t.id} ticket={t} busy={busyIds.has(t.id)}
                        onStatusChange={onStatusChange} />
          ))}
        </div>
      )}
    </div>
  );
}
