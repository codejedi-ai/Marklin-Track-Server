import type {
  GraphData, CIDetail, IngestResult, AskResponse,
  Chat, ChatSummary,
  Ticket, Suggestion, Status, TicketDraft,
} from "./types";

export type StreamEvent =
  | { type: "thought"; content: string }
  | { type: "done";
      answer: string;
      cypher?: string | null;
      rows?: Record<string, unknown>[] | null;
      thoughts?: string[] | null;
    }
  | { type: "error"; message: string };

const BASE = import.meta.env.VITE_API_BASE ?? "";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" } : undefined,
      ...init,
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?", 0);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : detail;
    } catch { /* ignore */ }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // --- CMDB ----------------------------------------------------------------
  graph: () => request<GraphData>("/api/graph"),
  listDevices: () => request<Record<string, unknown>[]>("/devices"),
  listUsers: () => request<Record<string, unknown>[]>("/users"),
  listApps: () => request<Record<string, unknown>[]>("/apps"),
  getCi: (identifier: string) =>
    request<CIDetail>(`/ci/${encodeURIComponent(identifier)}`),

  ingestFiles: (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return request<IngestResult[]>("/ingest", { method: "POST", body: fd });
  },
  ingestSamples: () =>
    request<IngestResult[]>("/ingest/samples", { method: "POST" }),

  ask: (question: string) =>
    request<AskResponse>("/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  health: () => request<{ status: string; backend: string }>("/health"),

  // --- Chats ---------------------------------------------------------------
  listChats: () => request<ChatSummary[]>("/api/chats"),
  createChat: (title?: string) =>
    request<Chat>("/api/chats", {
      method: "POST",
      body: JSON.stringify({ title: title ?? null }),
    }),
  getChat: (id: string) => request<Chat>(`/api/chats/${id}`),
  renameChat: (id: string, title: string) =>
    request<Chat>(`/api/chats/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteChat: (id: string) =>
    request<void>(`/api/chats/${id}`, { method: "DELETE" }),
  sendChatMessage: (id: string, question: string) =>
    request<Chat>(`/api/chats/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  /**
   * Stream a chat reply as NDJSON: each thought arrives as it's produced, then a
   * final {type:"done", answer, cypher, rows} or {type:"error", message}.
   */
  streamChatMessage: async (
    id: string,
    question: string,
    onEvent: (e: StreamEvent) => void,
  ) => {
    const res = await fetch(`${BASE}/api/chats/${id}/messages/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok || !res.body) {
      throw new ApiError(`Stream failed (${res.status})`, res.status);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (line) {
          try { onEvent(JSON.parse(line) as StreamEvent); }
          catch { /* malformed line — skip */ }
        }
      }
    }
    if (buf.trim()) {
      try { onEvent(JSON.parse(buf) as StreamEvent); } catch { /* */ }
    }
  },

  // --- Tickets (legacy) ----------------------------------------------------
  listTickets: () => request<Ticket[]>("/api/tickets"),
  suggest: (input: { title: string; description: string; email?: string }) =>
    request<Suggestion>("/api/ai/suggest", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  createTicket: (draft: TicketDraft) =>
    request<Ticket>("/api/tickets", {
      method: "POST",
      body: JSON.stringify({
        title: draft.title, description: draft.description,
        email: draft.email || null, department: draft.department || null,
        priority: draft.priority || null, category: draft.category || null,
        tags: draft.tags, suggested_response: draft.suggested_response || null,
        related_cis: draft.related_cis,
      }),
    }),
  updateStatus: (id: string, status: Status) =>
    request<Ticket>(`/api/tickets/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
};

export { ApiError };
