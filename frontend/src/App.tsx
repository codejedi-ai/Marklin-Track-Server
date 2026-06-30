import { useCallback, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { GraphView } from "./components/GraphView";
import { UploadView } from "./components/UploadView";
import { BrowseView } from "./components/BrowseView";
import { ChatView } from "./components/ChatView";

type Toast = { id: number; msg: string; tone: "success" | "error" };

export default function App() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  // Bumping this forces GraphView to remount + reload after an ingest.
  const [graphKey, setGraphKey] = useState(0);

  const notify = useCallback((msg: string, tone: "success" | "error") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
  }, []);

  const handleIngested = useCallback(() => {
    setGraphKey((k) => k + 1);
  }, []);

  return (
    <div className="flex h-screen">
      <Sidebar />

      <main className="flex flex-1 flex-col overflow-hidden">
        <Routes>
          <Route path="/" element={<Navigate to="/graph" replace />} />
          <Route path="/graph" element={<GraphView key={graphKey} />} />
          <Route path="/upload" element={<UploadView notify={notify} onIngested={handleIngested} />} />
          <Route path="/browse" element={<BrowseView />} />
          <Route path="/chat" element={<ChatView />} />
          <Route path="/chat/:chatId" element={<ChatView />} />
          <Route path="*" element={<Navigate to="/graph" replace />} />
        </Routes>
      </main>

      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto rounded-lg px-4 py-2 text-sm font-medium text-white shadow-lg ${
              t.tone === "success" ? "bg-emerald-600" : "bg-red-600"
            }`}
          >
            {t.msg}
          </div>
        ))}
      </div>
    </div>
  );
}
