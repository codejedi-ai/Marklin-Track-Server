import { useEffect, useMemo, useRef, useState } from "react";
import { Network } from "vis-network/standalone";
import { api, ApiError } from "../api";
import type { GraphData, GraphNode } from "../types";
import { Spinner } from "./ui";

// Distinct hues per CI label so the topology is readable at a glance.
const LABEL_COLOR: Record<string, { bg: string; border: string }> = {
  Device:          { bg: "#dbeafe", border: "#2563eb" },
  User:            { bg: "#dcfce7", border: "#16a34a" },
  App:             { bg: "#fef3c7", border: "#d97706" },
  Location:        { bg: "#e0e7ff", border: "#6366f1" },
  Department:      { bg: "#fae8ff", border: "#a855f7" },
  Team:            { bg: "#ffe4e6", border: "#e11d48" },
  OperatingSystem: { bg: "#cffafe", border: "#0891b2" },
};
const DEFAULT_COLOR = { bg: "#f1f5f9", border: "#64748b" };

function colorFor(label: string) {
  return LABEL_COLOR[label] ?? DEFAULT_COLOR;
}

export function GraphView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await api.graph());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load graph.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  // Build vis-network nodes/edges + render.
  useEffect(() => {
    if (!containerRef.current || !data) return;
    const nodes = data.nodes.map((n) => {
      const c = colorFor(n.label);
      return {
        id: n.id,
        label: n.display,
        title: `${n.label}: ${n.display}`,
        group: n.label,
        color: { background: c.bg, border: c.border, highlight: c },
        font: { size: 13, color: "#0f172a" },
        shape: "dot" as const,
        size: n.label === "Device" || n.label === "User" || n.label === "App" ? 18 : 12,
      };
    });
    const edges = data.edges.map((e, i) => ({
      id: `e${i}`, from: e.source, to: e.target, label: e.type,
      arrows: "to", color: { color: "#cbd5e1" },
      font: { size: 10, color: "#64748b", strokeWidth: 0, align: "middle" as const },
      smooth: { enabled: true, type: "continuous", roundness: 0.5 },
    }));
    const network = new Network(
      containerRef.current,
      { nodes, edges },
      {
        physics: { stabilization: { iterations: 150 },
                   barnesHut: { gravitationalConstant: -8000, springLength: 120 } },
        interaction: { hover: true, tooltipDelay: 200 },
        edges: { arrows: { to: { scaleFactor: 0.6 } } },
      },
    );
    networkRef.current = network;
    network.on("click", (params: { nodes: string[] }) => {
      const id = params.nodes?.[0];
      const node = id ? data.nodes.find((n) => n.id === id) ?? null : null;
      setSelected(node);
    });
    return () => network.destroy();
  }, [data]);

  const legend = useMemo(() => {
    const counts = new Map<string, number>();
    data?.nodes.forEach((n) => counts.set(n.label, (counts.get(n.label) ?? 0) + 1));
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [data]);

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Knowledge Graph</h1>
          <p className="text-xs text-slate-500">
            {data ? `${data.nodes.length} nodes · ${data.edges.length} edges` : "loading…"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {loading && <Spinner className="text-brand-600" />}
          <button onClick={load}
            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
            Reload
          </button>
        </div>
      </header>

      <div className="relative flex-1 bg-slate-50">
        {error && (
          <div className="absolute left-6 top-6 z-10 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}
        {!loading && data && data.nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="rounded-lg border border-dashed border-slate-300 bg-white px-8 py-6 text-center">
              <p className="text-sm font-medium text-slate-700">Graph is empty</p>
              <p className="mt-1 text-xs text-slate-500">Use the Upload tab to ingest data.</p>
            </div>
          </div>
        )}
        <div ref={containerRef} className="h-full w-full" />

        {/* Legend */}
        {legend.length > 0 && (
          <div className="absolute bottom-4 left-4 rounded-md border border-slate-200 bg-white/90 px-3 py-2 text-xs shadow-sm backdrop-blur">
            <div className="mb-1 font-semibold text-slate-700">Legend</div>
            <ul className="space-y-1">
              {legend.map(([label, n]) => {
                const c = colorFor(label);
                return (
                  <li key={label} className="flex items-center gap-2 text-slate-600">
                    <span className="inline-block h-2.5 w-2.5 rounded-full"
                          style={{ background: c.bg, border: `1.5px solid ${c.border}` }} />
                    <span className="font-medium">{label}</span>
                    <span className="text-slate-400">({n})</span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* Detail panel */}
        {selected && (
          <div className="absolute right-4 top-4 w-72 rounded-md border border-slate-200 bg-white p-4 shadow-md">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {selected.label}
                </div>
                <div className="mt-0.5 text-sm font-semibold text-slate-900">
                  {selected.display}
                </div>
              </div>
              <button onClick={() => setSelected(null)}
                      className="text-slate-400 hover:text-slate-600">×</button>
            </div>
            <dl className="mt-3 space-y-1 text-xs">
              {Object.entries(selected.props)
                .filter(([k]) => !k.startsWith("_"))
                .slice(0, 10)
                .map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3">
                    <dt className="font-medium text-slate-500">{k}</dt>
                    <dd className="truncate text-right text-slate-700">{String(v)}</dd>
                  </div>
                ))}
            </dl>
          </div>
        )}
      </div>
    </div>
  );
}
