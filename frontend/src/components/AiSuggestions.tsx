import { useState } from "react";
import type { Priority, Suggestion } from "../types";
import { Chip } from "./ui";

const PRIORITIES: Priority[] = ["Low", "Medium", "High"];
const CATEGORIES = ["Network", "Access", "Software", "General"];

/**
 * Shows the AI suggestion as an EDITABLE panel. The user can tweak every field
 * before clicking "Use Suggestion", which applies the (possibly edited) values to
 * the ticket draft. This gives clear user control over the AI output.
 */
export function AiSuggestions({
  suggestion, onUse, onDismiss,
}: {
  suggestion: Suggestion;
  onUse: (s: Suggestion) => void;
  onDismiss: () => void;
}) {
  const [category, setCategory] = useState(suggestion.category);
  const [priority, setPriority] = useState<Priority>(suggestion.priority);
  const [tags, setTags] = useState<string[]>(suggestion.tags);
  const [response, setResponse] = useState(suggestion.suggested_response);
  const [tagInput, setTagInput] = useState("");

  const addTag = () => {
    const t = tagInput.trim();
    if (t && !tags.includes(t)) setTags([...tags, t]);
    setTagInput("");
  };

  return (
    <div className="mt-4 rounded-xl border border-brand-200 bg-brand-50/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-brand-700">✨ AI Suggestions</span>
          {suggestion.grounded ? (
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
              Grounded in CMDB
            </span>
          ) : (
            <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600">
              Heuristic
            </span>
          )}
        </div>
        <button onClick={onDismiss} className="text-xs text-slate-400 hover:text-slate-600">
          Dismiss
        </button>
      </div>

      {suggestion.related_cis.length > 0 && (
        <div className="mb-3">
          <span className="mb-1 block text-xs font-medium text-slate-500">
            Related configuration items
          </span>
          <div className="flex flex-wrap gap-1.5">
            {suggestion.related_cis.map((ci, i) => (
              <Chip key={i} tone="brand">
                {ci.type}: {ci.name ?? ci.id}
              </Chip>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Category</span>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          >
            {[category, ...CATEGORIES.filter((c) => c !== category)].map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Priority</span>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as Priority)}
            className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          >
            {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
      </div>

      <div className="mt-3">
        <span className="mb-1 block text-xs font-medium text-slate-600">Tags</span>
        <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-slate-300 bg-white p-2">
          {tags.map((t) => (
            <span key={t} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs">
              {t}
              <button onClick={() => setTags(tags.filter((x) => x !== t))}
                      className="text-slate-400 hover:text-slate-700">×</button>
            </span>
          ))}
          <input
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTag(); } }}
            placeholder="add tag…"
            className="min-w-[80px] flex-1 text-sm outline-none"
          />
        </div>
      </div>

      <div className="mt-3">
        <span className="mb-1 block text-xs font-medium text-slate-600">Suggested response</span>
        <textarea
          value={response}
          onChange={(e) => setResponse(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
        />
      </div>

      <div className="mt-4 flex justify-end">
        <button
          onClick={() => onUse({ ...suggestion, category, priority, tags, suggested_response: response })}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
        >
          Use Suggestion
        </button>
      </div>
    </div>
  );
}
