import type { Status, Ticket } from "../types";
import { Chip, PriorityBadge, StatusBadge } from "./ui";

const STATUSES: Status[] = ["New", "In Progress", "Resolved"];

export function TicketCard({
  ticket, onStatusChange, busy,
}: {
  ticket: Ticket;
  onStatusChange: (id: string, status: Status) => void;
  busy: boolean;
}) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="truncate font-semibold text-slate-900">{ticket.title}</h3>
            <span className="shrink-0 text-xs text-slate-400">{ticket.id}</span>
          </div>
          {ticket.email && (
            <p className="mt-0.5 text-xs text-slate-400">{ticket.email}</p>
          )}
        </div>
        <PriorityBadge value={ticket.priority} />
      </div>

      {ticket.description && (
        <p className="mt-2 line-clamp-3 text-sm text-slate-600">{ticket.description}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {ticket.category && <Chip tone="brand">{ticket.category}</Chip>}
        {ticket.tags.map((t) => <Chip key={t}>{t}</Chip>)}
      </div>

      {ticket.suggested_response && (
        <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
          <span className="mb-0.5 block text-xs font-semibold text-slate-400">
            AI suggested response
          </span>
          {ticket.suggested_response}
        </div>
      )}

      <div className="mt-4 flex items-center justify-between">
        <StatusBadge value={ticket.status} />
        <label className="flex items-center gap-2 text-xs text-slate-500">
          <span>Status</span>
          <select
            value={ticket.status}
            disabled={busy}
            onChange={(e) => onStatusChange(ticket.id, e.target.value as Status)}
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs
              focus:border-brand-500 focus:ring-2 focus:ring-brand-100 outline-none disabled:opacity-50"
          >
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
      </div>
    </article>
  );
}
