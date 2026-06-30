import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { CIDetail } from "../types";
import { Chip, Spinner } from "./ui";

type Kind = "Device" | "User" | "App";
const KINDS: Kind[] = ["Device", "User", "App"];

const ID_FIELD: Record<Kind, string[]> = {
  Device: ["device_id", "hostname"],
  User:   ["uid", "email", "name"],
  App:    ["name_norm", "name", "app_id"],
};
const DISPLAY_FIELD: Record<Kind, string[]> = {
  Device: ["hostname", "device_id"],
  User:   ["name", "email"],
  App:    ["name"],
};

function pick(obj: Record<string, unknown>, fields: string[]): string {
  for (const f of fields) {
    const v = obj[f];
    if (v != null && String(v).trim()) return String(v);
  }
  return "—";
}

export function BrowseView() {
  const [kind, setKind] = useState<Kind>("Device");
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<CIDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null); setSelected(null);
    try {
      const fn = kind === "Device" ? api.listDevices
              : kind === "User" ? api.listUsers : api.listApps;
      setItems(await fn());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load.");
    } finally {
      setLoading(false);
    }
  }, [kind]);

  useEffect(() => { load(); }, [load]);

  async function openDetail(item: Record<string, unknown>) {
    const ident = pick(item, ID_FIELD[kind]);
    if (ident === "—") return;
    setDetailLoading(true);
    try {
      setSelected(await api.getCi(ident));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load detail.");
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <h1 className="text-lg font-semibold text-slate-900">Browse CIs</h1>
        <p className="text-xs text-slate-500">
          Configuration Items in the graph, by type.
        </p>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden border-r border-slate-200">
          <div className="flex items-center gap-2 border-b border-slate-200 bg-white px-6 py-2">
            {KINDS.map((k) => (
              <button
                key={k}
                onClick={() => setKind(k)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  kind === k
                    ? "bg-brand-100 text-brand-700"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {k}s
              </button>
            ))}
            <span className="ml-auto text-xs text-slate-400">
              {loading ? "…" : `${items.length} items`}
            </span>
          </div>

          <div className="flex-1 overflow-auto p-6">
            {loading ? (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Spinner /> Loading…
              </div>
            ) : error ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            ) : items.length === 0 ? (
              <div className="text-sm text-slate-500">
                No {kind.toLowerCase()}s in the graph. Use the Upload tab to ingest data.
              </div>
            ) : (
              <ul className="space-y-2">
                {items.map((it, i) => (
                  <li key={i}>
                    <button
                      onClick={() => openDetail(it)}
                      className="flex w-full items-center justify-between rounded-md border border-slate-200 bg-white px-4 py-3 text-left hover:border-brand-300 hover:bg-brand-50"
                    >
                      <div>
                        <div className="text-sm font-semibold text-slate-900">
                          {pick(it, DISPLAY_FIELD[kind])}
                        </div>
                        <div className="mt-0.5 font-mono text-xs text-slate-500">
                          {pick(it, ID_FIELD[kind])}
                        </div>
                      </div>
                      {Array.isArray(it._sources) && (
                        <span className="text-xs text-slate-400">
                          {(it._sources as string[]).length} source{(it._sources as string[]).length === 1 ? "" : "s"}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <aside className="flex w-96 flex-col overflow-hidden bg-slate-50">
          <div className="border-b border-slate-200 bg-white px-6 py-3 text-sm font-semibold text-slate-700">
            Detail
          </div>
          <div className="flex-1 overflow-auto p-6">
            {detailLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Spinner /> Loading…
              </div>
            ) : !selected ? (
              <p className="text-sm text-slate-400">
                Select a CI on the left to see its properties and relationships.
              </p>
            ) : (
              <>
                <h3 className="text-sm font-semibold text-slate-900">
                  {pick(selected.ci, DISPLAY_FIELD[kind])}
                </h3>
                <dl className="mt-3 space-y-1 text-xs">
                  {Object.entries(selected.ci)
                    .filter(([k]) => !k.startsWith("_"))
                    .map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-3">
                        <dt className="font-medium text-slate-500">{k}</dt>
                        <dd className="truncate text-right text-slate-700">
                          {Array.isArray(v) ? v.join(", ") : String(v)}
                        </dd>
                      </div>
                    ))}
                </dl>

                <h4 className="mt-5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Relationships ({selected.relationships.length})
                </h4>
                <ul className="mt-2 space-y-2">
                  {selected.relationships.map((r, i) => {
                    const nm = (r.node.name || r.node.hostname || r.node.email
                                || r.node.device_id || r.node.app_id || r.node.uid || "?") as string;
                    return (
                      <li key={i} className="rounded border border-slate-200 bg-white px-3 py-2 text-sm">
                        <Chip tone="brand">
                          {r.direction === "out" ? "→" : "←"} {r.rel}
                        </Chip>
                        <span className="ml-2 text-slate-700">{nm}</span>
                      </li>
                    );
                  })}
                </ul>

                {selected.ci._sources && Array.isArray(selected.ci._sources) && (
                  <div className="mt-5 text-xs text-slate-400">
                    Sources: {(selected.ci._sources as string[]).join(", ")}
                  </div>
                )}
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
