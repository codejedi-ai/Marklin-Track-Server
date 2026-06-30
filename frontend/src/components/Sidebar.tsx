import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../api";

const NAV = [
  { to: "/graph",  label: "Knowledge Graph", icon: "◉" },
  { to: "/upload", label: "Upload Data",     icon: "↥" },
  { to: "/browse", label: "Browse CIs",      icon: "≡" },
  { to: "/chat",   label: "Ask AI",          icon: "✦" },
];

export function Sidebar() {
  const [health, setHealth] = useState<"loading" | "ok" | "down">("loading");
  const [backend, setBackend] = useState<string>("");

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const h = await api.health();
        if (!alive) return;
        setHealth("ok");
        setBackend(h.backend);
      } catch {
        if (alive) setHealth("down");
      }
    };
    tick();
    const id = setInterval(tick, 15000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-5 py-5">
        <div className="text-base font-bold tracking-tight text-slate-900">CMDB</div>
        <div className="text-xs text-slate-500">AI knowledge graph</div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            className={({ isActive }) =>
              `flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition ${
                isActive
                  ? "bg-brand-600 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`
            }
          >
            <span className="w-4 text-center" aria-hidden="true">{n.icon}</span>
            <span>{n.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-slate-200 px-5 py-3 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2 w-2 rounded-full ${
            health === "ok" ? "bg-emerald-500"
            : health === "down" ? "bg-red-500" : "bg-slate-300"
          }`} />
          <span>{health === "ok" ? `backend: ${backend}` : health === "down" ? "backend offline" : "checking…"}</span>
        </div>
      </div>
    </aside>
  );
}
