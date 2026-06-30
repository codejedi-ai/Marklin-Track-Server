import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy API calls to the FastAPI backend in dev (avoids CORS fuss).
    // Proxy every backend route. The agent API mixes "/api/*" (tickets, graph)
    // with bare paths ("/health", "/devices", "/ci/...", "/ask", "/ingest").
    proxy: {
      "/api":      "http://localhost:8000",
      "/health":   "http://localhost:8000",
      "/devices":  "http://localhost:8000",
      "/users":    "http://localhost:8000",
      "/apps":     "http://localhost:8000",
      "/ci":       "http://localhost:8000",
      "/ask":      "http://localhost:8000",
      "/ingest":   "http://localhost:8000",
    },
  },
});
