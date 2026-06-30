import { useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { IngestResult } from "../types";
import { Spinner } from "./ui";

export function UploadView({
  notify, onIngested,
}: {
  notify: (msg: string, tone: "success" | "error") => void;
  onIngested: () => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState<IngestResult[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | File[]) {
    const arr = Array.from(list);
    setFiles((prev) => [...prev, ...arr]);
  }

  async function handleUpload() {
    if (!files.length) return;
    setSubmitting(true);
    try {
      const res = await api.ingestFiles(files);
      setResults(res);
      const totalNodes = res.reduce((n, r) => n + r.nodes_written, 0);
      const totalEdges = res.reduce((n, r) => n + r.edges_written, 0);
      notify(`Ingested ${files.length} file(s): ${totalNodes} nodes, ${totalEdges} edges.`,
             "success");
      setFiles([]);
      onIngested();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Ingest failed.", "error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSamples() {
    setSubmitting(true);
    try {
      const res = await api.ingestSamples();
      setResults(res);
      const totalNodes = res.reduce((n, r) => n + r.nodes_written, 0);
      const totalEdges = res.reduce((n, r) => n + r.edges_written, 0);
      notify(`Loaded samples: ${totalNodes} nodes, ${totalEdges} edges.`, "success");
      onIngested();
    } catch (e) {
      notify(e instanceof ApiError ? e.message : "Sample ingest failed.", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-auto">
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <h1 className="text-lg font-semibold text-slate-900">Upload Data</h1>
        <p className="text-xs text-slate-500">
          Ingest CSV / JSON / YAML exports — they layer into the knowledge graph.
        </p>
      </header>

      <div className="space-y-6 p-6">
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault(); setDragging(false);
            addFiles(e.dataTransfer.files);
          }}
          className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 transition ${
            dragging ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white"
          }`}
        >
          <div className="text-4xl text-slate-400">↥</div>
          <p className="mt-2 text-sm font-medium text-slate-700">
            Drop files here, or
          </p>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="mt-2 rounded-md border border-slate-300 bg-white px-4 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Browse files
          </button>
          <input
            ref={inputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
            accept=".csv,.json,.yaml,.yml,.txt"
          />
          <p className="mt-2 text-xs text-slate-400">
            Accepts hardware CSV/JSON/YAML, Okta JSON, app inventory.
          </p>
        </div>

        {files.length > 0 && (
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-700">
                Queued ({files.length})
              </h3>
              <button
                onClick={() => setFiles([])}
                className="text-xs text-slate-500 hover:text-slate-700"
              >
                Clear
              </button>
            </div>
            <ul className="space-y-1 text-sm">
              {files.map((f, i) => (
                <li key={i} className="flex items-center justify-between rounded-md border border-slate-100 px-3 py-2">
                  <span className="truncate font-mono text-xs text-slate-700">{f.name}</span>
                  <span className="text-xs text-slate-400">{(f.size / 1024).toFixed(1)} KB</span>
                </li>
              ))}
            </ul>
            <button
              onClick={handleUpload}
              disabled={submitting}
              className="mt-4 inline-flex items-center gap-2 rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {submitting ? <Spinner /> : null}
              {submitting ? "Ingesting…" : `Ingest ${files.length} file(s)`}
            </button>
          </div>
        )}

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <h3 className="text-sm font-semibold text-slate-700">Or load bundled samples</h3>
          <p className="mt-1 text-xs text-slate-500">
            Loads the take-home sample dataset (hardware + Okta + app inventory)
            from <code>input_data/backend</code>.
          </p>
          <button
            onClick={handleSamples}
            disabled={submitting}
            className="mt-3 inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            {submitting ? <Spinner /> : null}
            Load samples
          </button>
        </div>

        {results.length > 0 && (
          <div className="rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">
              Ingest results
            </div>
            <table className="w-full text-xs">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-4 py-2 font-medium">File</th>
                  <th className="px-4 py-2 font-medium">Detected</th>
                  <th className="px-4 py-2 text-right font-medium">Nodes</th>
                  <th className="px-4 py-2 text-right font-medium">Edges</th>
                  <th className="px-4 py-2 font-medium">Errors</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-4 py-2 font-mono">{r.source}</td>
                    <td className="px-4 py-2 text-slate-600">{r.detected}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{r.nodes_written}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{r.edges_written}</td>
                    <td className="px-4 py-2 text-red-600">{r.errors?.join("; ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
