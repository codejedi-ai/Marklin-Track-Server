import { useState } from "react";
import type { Priority, Suggestion, Ticket, TicketDraft } from "../types";
import { api, ApiError } from "../api";
import { AiSuggestions } from "./AiSuggestions";
import { Field, Spinner, Chip, PriorityBadge } from "./ui";

const EMPTY: TicketDraft = {
  title: "", description: "", email: "", department: "", priority: "",
  category: "", tags: [], suggested_response: "", related_cis: [],
};

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "focus:border-brand-500 focus:ring-2 focus:ring-brand-100 outline-none";

export function TicketForm({
  onCreated, notify,
}: {
  onCreated: (t: Ticket) => void;
  notify: (msg: string, tone: "success" | "error") => void;
}) {
  const [draft, setDraft] = useState<TicketDraft>(EMPTY);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const set = (patch: Partial<TicketDraft>) => setDraft((d) => ({ ...d, ...patch }));
  const applied = draft.category !== "" || draft.tags.length > 0;

  async function handleSuggest() {
    if (!draft.title.trim()) {
      setSuggestError("Add a title first so the AI has something to work with.");
      return;
    }
    setSuggesting(true);
    setSuggestError(null);
    setSuggestion(null);
    try {
      const s = await api.suggest({
        title: draft.title,
        description: draft.description,
        email: draft.email || undefined,
      });
      setSuggestion(s);
    } catch (e) {
      setSuggestError(e instanceof ApiError ? e.message : "Failed to get suggestions.");
    } finally {
      setSuggesting(false);
    }
  }

  function handleUse(s: Suggestion) {
    set({
      category: s.category,
      priority: s.priority,
      tags: s.tags,
      suggested_response: s.suggested_response,
      related_cis: s.related_cis,
    });
    setSuggestion(null);
    notify("AI suggestions applied to the ticket.", "success");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.title.trim()) {
      notify("A title is required.", "error");
      return;
    }
    setSubmitting(true);
    try {
      const ticket = await api.createTicket(draft);
      onCreated(ticket);
      setDraft(EMPTY);
      setSuggestion(null);
      notify(`Ticket ${ticket.id} created.`, "success");
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Failed to create ticket.", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-1 text-lg font-semibold text-slate-900">Report an issue</h2>
      <p className="mb-5 text-sm text-slate-500">
        Describe the problem, then let AI triage it using your IT inventory.
      </p>

      <div className="space-y-4">
        <Field label="Title">
          <input
            className={inputCls}
            value={draft.title}
            onChange={(e) => set({ title: e.target.value })}
            placeholder="e.g. Can't access Slack"
          />
        </Field>

        <Field label="Description">
          <textarea
            className={inputCls}
            rows={4}
            value={draft.description}
            onChange={(e) => set({ description: e.target.value })}
            placeholder="What happened? Any error messages?"
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Email" hint="Used to ground suggestions in your CMDB profile.">
            <input
              type="email"
              className={inputCls}
              value={draft.email}
              onChange={(e) => set({ email: e.target.value })}
              placeholder="you@example.com"
            />
          </Field>
          <Field label="Department (optional)">
            <input
              className={inputCls}
              value={draft.department}
              onChange={(e) => set({ department: e.target.value })}
              placeholder="Engineering"
            />
          </Field>
        </div>

        <Field label="Priority (optional)">
          <select
            className={inputCls}
            value={draft.priority}
            onChange={(e) => set({ priority: e.target.value as Priority | "" })}
          >
            <option value="">— let AI decide —</option>
            <option value="Low">Low</option>
            <option value="Medium">Medium</option>
            <option value="High">High</option>
          </select>
        </Field>
      </div>

      {/* AI action */}
      <div className="mt-5 flex items-center gap-3">
        <button
          type="button"
          onClick={handleSuggest}
          disabled={suggesting}
          className="inline-flex items-center gap-2 rounded-lg border border-brand-300 bg-brand-50
            px-4 py-2 text-sm font-semibold text-brand-700 hover:bg-brand-100 disabled:opacity-60"
        >
          {suggesting ? <Spinner className="text-brand-600" /> : "✨"}
          {suggesting ? "Analyzing…" : "Generate AI Suggestions"}
        </button>
        {applied && !suggestion && (
          <span className="text-xs text-emerald-600">✓ suggestions applied</span>
        )}
      </div>

      {suggestError && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {suggestError}
        </div>
      )}

      {suggestion && (
        <AiSuggestions suggestion={suggestion} onUse={handleUse}
                       onDismiss={() => setSuggestion(null)} />
      )}

      {/* applied summary */}
      {applied && (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 px-3 py-2">
          <span className="text-xs font-medium text-slate-500">Will submit as:</span>
          {draft.category && <Chip>{draft.category}</Chip>}
          {draft.priority && <PriorityBadge value={draft.priority as Priority} />}
          {draft.tags.map((t) => <Chip key={t}>{t}</Chip>)}
        </div>
      )}

      <div className="mt-6 flex justify-end">
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2.5
            text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {submitting && <Spinner />}
          {submitting ? "Submitting…" : "Submit ticket"}
        </button>
      </div>
    </form>
  );
}
