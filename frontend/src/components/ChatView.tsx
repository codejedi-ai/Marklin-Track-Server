import { useCallback, useEffect, useRef, useState } from "react";
/* eslint-disable react-hooks/exhaustive-deps */
import { NavLink, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, ApiError } from "../api";
import type { Chat, ChatMessage, ChatSummary } from "../types";
import { Spinner } from "./ui";

// Compact markdown renderer for assistant messages. Tailwind classes scope the
// styles so headings, lists, code, tables etc. read well inside a chat bubble.
const MD_COMPONENTS = {
  p:  (props: any) => <p className="my-1 leading-snug" {...props} />,
  ul: (props: any) => <ul className="my-1 list-disc pl-5" {...props} />,
  ol: (props: any) => <ol className="my-1 list-decimal pl-5" {...props} />,
  li: (props: any) => <li className="my-0.5" {...props} />,
  h1: (props: any) => <h1 className="mt-2 mb-1 text-base font-bold" {...props} />,
  h2: (props: any) => <h2 className="mt-2 mb-1 text-sm font-bold" {...props} />,
  h3: (props: any) => <h3 className="mt-2 mb-1 text-sm font-semibold" {...props} />,
  a:  (props: any) => (
    <a className="text-brand-700 underline hover:text-brand-800" target="_blank"
       rel="noreferrer" {...props} />
  ),
  code: (props: any) => {
    const isBlock = props.className?.includes("language-");
    if (isBlock) {
      return (
        <pre className="my-2 overflow-auto rounded bg-slate-100 px-3 py-2 font-mono text-[11px] text-slate-800">
          <code {...props} />
        </pre>
      );
    }
    return (
      <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[12px] text-slate-800">
        {props.children}
      </code>
    );
  },
  blockquote: (props: any) => (
    <blockquote className="my-1 border-l-2 border-slate-300 pl-3 text-slate-600" {...props} />
  ),
  table: (props: any) => (
    <div className="my-2 overflow-auto">
      <table className="w-full border-collapse text-xs" {...props} />
    </div>
  ),
  th: (props: any) => <th className="border border-slate-200 bg-slate-50 px-2 py-1 text-left font-semibold" {...props} />,
  td: (props: any) => <td className="border border-slate-200 px-2 py-1" {...props} />,
  hr: () => <hr className="my-2 border-slate-200" />,
} as const;

const SUGGESTED = [
  "Which users do not have MFA enabled?",
  "How many users use Slack?",
  "Show all inactive devices.",
  "Who is in the DevOps team?",
];

function fmtTime(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return sameDay
    ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString();
}

export function ChatView() {
  const { chatId } = useParams<{ chatId?: string }>();
  const navigate = useNavigate();

  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [chatsLoading, setChatsLoading] = useState(true);
  const [chat, setChat] = useState<Chat | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");

  const scrollRef = useRef<HTMLDivElement>(null);
  // Skip the server-side chat reload for ids we just created locally — otherwise
  // the optimistic user+assistant bubbles get wiped when streaming starts.
  const skipNextLoadRef = useRef<string | null>(null);
  // While streaming, don't let the chatId effect overwrite the streaming state.
  const streamingRef = useRef(false);

  const refreshChats = useCallback(async () => {
    try {
      setChats(await api.listChats());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load chats.");
    } finally {
      setChatsLoading(false);
    }
  }, []);

  useEffect(() => { refreshChats(); }, [refreshChats]);

  // Load the selected chat whenever the URL id changes.
  useEffect(() => {
    if (!chatId) { setChat(null); return; }
    // Don't refetch a chat we just created (we already set local state) or one
    // we're actively streaming a reply into.
    if (skipNextLoadRef.current === chatId) {
      skipNextLoadRef.current = null;
      return;
    }
    if (streamingRef.current) return;
    let cancelled = false;
    setChatLoading(true);
    setError(null);
    api.getChat(chatId)
      .then((c) => { if (!cancelled) setChat(c); })
      .catch((e) => {
        if (cancelled) return;
        // If a chat was deleted in another tab the URL goes stale — bounce.
        if (e instanceof ApiError && e.status === 404) {
          navigate("/chat", { replace: true });
        } else {
          setError(e instanceof ApiError ? e.message : "Failed to load chat.");
        }
      })
      .finally(() => { if (!cancelled) setChatLoading(false); });
    return () => { cancelled = true; };
  }, [chatId, navigate]);

  const msgs = chat?.messages ?? [];
  const lastThoughtCount = msgs.length ? (msgs[msgs.length - 1].thoughts?.length ?? 0) : 0;
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    // Re-run on every new streamed thought so the bubble stays in view.
  }, [chat?.messages.length, lastThoughtCount, busy]);

  async function startNewChat() {
    try {
      const c = await api.createChat();
      await refreshChats();
      navigate(`/chat/${c.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to create chat.");
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.deleteChat(id);
      if (id === chatId) navigate("/chat", { replace: true });
      await refreshChats();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to delete chat.");
    }
  }

  function startEditTitle() {
    if (!chat) return;
    setDraftTitle(chat.title);
    setEditingTitle(true);
  }

  async function commitTitle() {
    if (!chat) return;
    const trimmed = draftTitle.trim();
    setEditingTitle(false);
    if (!trimmed || trimmed === chat.title) return;
    const previous = chat.title;
    setChat({ ...chat, title: trimmed });           // optimistic
    try {
      const updated = await api.renameChat(chat.id, trimmed);
      setChat(updated);
      await refreshChats();
    } catch (e) {
      setChat((c) => (c ? { ...c, title: previous } : c)); // revert
      setError(e instanceof ApiError ? e.message : "Failed to rename chat.");
    }
  }

  async function handleSend(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setBusy(true);
    setInput("");
    streamingRef.current = true;
    try {
      // No selected chat yet: create one, then send.
      let id = chatId;
      if (!id) {
        const created = await api.createChat();
        id = created.id;
        skipNextLoadRef.current = id;     // don't refetch — we have the fresh state
        setChat(created);
        navigate(`/chat/${id}`, { replace: true });
      }

      const now = new Date().toISOString();
      // Optimistically append the user msg + an empty assistant msg we'll
      // mutate as thoughts stream in.
      setChat((c) => c ? {
        ...c,
        messages: [
          ...c.messages,
          { role: "user", content: q, ts: now },
          { role: "assistant", content: "", thoughts: [], ts: now },
        ],
      } : c);

      const patchAssistant = (patch: Partial<ChatMessage>) => {
        setChat((c) => {
          if (!c) return c;
          const msgs = c.messages.slice();
          const last = msgs[msgs.length - 1];
          if (last?.role !== "assistant") return c;
          msgs[msgs.length - 1] = { ...last, ...patch };
          return { ...c, messages: msgs };
        });
      };

      await api.streamChatMessage(id!, q, (ev) => {
        if (ev.type === "thought") {
          setChat((c) => {
            if (!c) return c;
            const msgs = c.messages.slice();
            const last = msgs[msgs.length - 1];
            if (last?.role !== "assistant") return c;
            msgs[msgs.length - 1] = {
              ...last,
              thoughts: [...(last.thoughts ?? []), ev.content],
            };
            return { ...c, messages: msgs };
          });
        } else if (ev.type === "done") {
          patchAssistant({
            content: ev.answer,
            cypher: ev.cypher ?? null,
            rows: ev.rows ?? null,
            thoughts: ev.thoughts ?? undefined,
          });
        } else if (ev.type === "error") {
          patchAssistant({ content: `Agent error: ${ev.message}` });
        }
      });

      await refreshChats();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to send message.");
    } finally {
      streamingRef.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Chat list */}
      <div className="flex w-72 shrink-0 flex-col border-r border-slate-200 bg-slate-50">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-700">Chats</h2>
          <button
            onClick={startNewChat}
            className="rounded-md bg-brand-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-brand-700"
          >
            + New
          </button>
        </div>

        <div className="flex-1 overflow-auto p-2">
          {chatsLoading ? (
            <div className="flex items-center gap-2 px-3 py-2 text-sm text-slate-500">
              <Spinner /> Loading…
            </div>
          ) : chats.length === 0 ? (
            <p className="px-3 py-4 text-xs text-slate-500">
              No chats yet. Start one with the <span className="font-semibold">+ New</span> button
              or by asking a question on the right.
            </p>
          ) : (
            <ul className="space-y-1">
              {chats.map((c) => (
                <li key={c.id} className="group relative">
                  <NavLink
                    to={`/chat/${c.id}`}
                    className={({ isActive }) =>
                      `block rounded-md py-2 pl-3 pr-9 text-sm transition ${
                        isActive
                          ? "bg-brand-100 text-brand-800"
                          : "text-slate-700 hover:bg-slate-100"
                      }`
                    }
                  >
                    <div className="truncate font-medium">{c.title}</div>
                    <div className="mt-0.5 flex items-center justify-between text-[11px] text-slate-500">
                      <span>{c.message_count} msg{c.message_count === 1 ? "" : "s"}</span>
                      <span>{fmtTime(c.updated_at)}</span>
                    </div>
                  </NavLink>
                  <button
                    onClick={(e) => { e.preventDefault(); handleDelete(c.id); }}
                    title="Delete chat"
                    aria-label="Delete chat"
                    className="absolute right-1.5 top-1/2 hidden h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-slate-400 hover:bg-red-100 hover:text-red-600 group-hover:flex"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Conversation panel */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <div className="flex items-baseline justify-between">
            <div className="min-w-0 flex-1">
              {editingTitle && chat ? (
                <input
                  autoFocus
                  value={draftTitle}
                  onChange={(e) => setDraftTitle(e.target.value)}
                  onBlur={commitTitle}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") { e.preventDefault(); commitTitle(); }
                    if (e.key === "Escape") { e.preventDefault(); setEditingTitle(false); }
                  }}
                  maxLength={120}
                  className="w-full max-w-xl rounded-md border border-brand-300 bg-white px-2 py-1 text-lg font-semibold text-slate-900 focus:border-brand-500 focus:ring-2 focus:ring-brand-100 outline-none"
                  aria-label="Chat title"
                />
              ) : (
                <h1
                  onClick={chat ? startEditTitle : undefined}
                  title={chat ? "Click to rename" : undefined}
                  className={`group flex items-center gap-2 text-lg font-semibold text-slate-900 ${
                    chat ? "cursor-text rounded-md px-1 -mx-1 hover:bg-slate-100" : ""
                  }`}
                >
                  <span className="truncate">{chat?.title || "Ask AI"}</span>
                  {chat && (
                    <span className="text-xs text-slate-400 opacity-0 transition group-hover:opacity-100"
                          aria-hidden="true">
                      ✎
                    </span>
                  )}
                </h1>
              )}
              <p className="text-xs text-slate-500">
                {chatId
                  ? <span className="font-mono">/chat/{chatId}</span>
                  : "Start a new conversation."}
              </p>
            </div>
            {chatLoading && <Spinner className="text-brand-600" />}
          </div>
        </header>

        <div ref={scrollRef} className="flex-1 space-y-4 overflow-auto bg-slate-50 p-6">
          {error && (
            <div className="mx-auto max-w-2xl rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {!chatId && (
            <div className="mx-auto max-w-xl rounded-lg border border-slate-200 bg-white p-5">
              <h3 className="text-sm font-semibold text-slate-700">Start a new chat</h3>
              <p className="mt-1 text-xs text-slate-500">
                Type a question below, or pick one of these to begin.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {SUGGESTED.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 hover:bg-brand-50 hover:text-brand-700"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {chat?.messages.map((m, i) => {
            if (m.role === "user") {
              return (
                <div key={i} className="flex justify-end">
                  <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-brand-600 px-4 py-2 text-sm text-white shadow-sm">
                    {m.content}
                  </div>
                </div>
              );
            }
            const isLast = i === (chat?.messages.length ?? 0) - 1;
            const isStreaming = busy && isLast && m.role === "assistant";
            const thoughtCount = m.thoughts?.length ?? 0;
            return (
              <div key={i} className="flex justify-start">
                <div className="min-w-[12rem] max-w-2xl space-y-3 rounded-2xl rounded-tl-sm bg-white px-4 py-3 text-sm text-slate-800 shadow-sm">
                  {!m.content && isStreaming && thoughtCount === 0 && (
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Spinner className="text-brand-600" /> Thinking…
                    </div>
                  )}
                  {(thoughtCount > 0 || isStreaming) && (
                    <details className="text-xs text-slate-500" open>
                      <summary className="flex cursor-pointer items-center gap-2 font-medium">
                        {isStreaming && (
                          <span className="relative inline-flex h-2 w-2" aria-label="streaming">
                            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-75" />
                            <span className="relative inline-flex h-2 w-2 rounded-full bg-brand-500" />
                          </span>
                        )}
                        Thought process ({thoughtCount} step{thoughtCount === 1 ? "" : "s"})
                        {isStreaming && <span className="text-brand-600">· streaming</span>}
                      </summary>
                      <ol className="mt-2 space-y-1 rounded bg-slate-50 px-3 py-2">
                        {(m.thoughts ?? []).map((t, j) => {
                          const isWrite = /run_write_cypher/i.test(t);
                          const isErr = /^Observation:.*\bERROR\b/i.test(t);
                          const head = t.split(":")[0];
                          return (
                            <li key={j} className="flex gap-2 font-mono text-[11px] leading-snug">
                              <span className={`shrink-0 font-semibold ${
                                head === "Thought" ? "text-violet-600"
                                : head === "Action" || head === "Action Input"
                                  ? (isWrite ? "text-orange-600" : "text-brand-600")
                                : head === "Observation"
                                  ? (isErr ? "text-red-600" : "text-emerald-600")
                                : head === "Answer" ? "text-slate-900"
                                : "text-slate-500"
                              }`}>{head}:</span>
                              <span className="break-all text-slate-700">
                                {t.slice(head.length + 1).trim()}
                              </span>
                            </li>
                          );
                        })}
                      </ol>
                    </details>
                  )}
                  {m.content && (
                    <div className="markdown break-words border-t border-slate-100 pt-3">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={MD_COMPONENTS}
                      >
                        {m.content}
                      </ReactMarkdown>
                    </div>
                  )}
                  {m.cypher && (
                    <details className="text-xs text-slate-500">
                      <summary className="cursor-pointer font-medium">Cypher</summary>
                      <pre className="mt-2 overflow-auto rounded bg-slate-100 px-3 py-2 font-mono text-[11px] text-slate-700">
{m.cypher}
                      </pre>
                    </details>
                  )}
                  {m.rows && m.rows.length > 0 && (
                    <details className="text-xs text-slate-500">
                      <summary className="cursor-pointer font-medium">
                        Rows ({m.rows.length})
                      </summary>
                      <pre className="mt-2 max-h-60 overflow-auto rounded bg-slate-100 px-3 py-2 font-mono text-[11px] text-slate-700">
{JSON.stringify(m.rows, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            );
          })}

        </div>

        <form
          onSubmit={(e) => { e.preventDefault(); handleSend(input); }}
          className="flex items-center gap-2 border-t border-slate-200 bg-white px-6 py-3"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={busy}
            placeholder={chatId ? "Reply…" : "Ask anything to start a new chat…"}
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-100 outline-none"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
