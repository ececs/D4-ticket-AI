/**
 * ChatSidebar — floating AI assistant panel.
 *
 * Architecture:
 *  - Conversation history is stored in local component state (array of ChatMessage).
 *  - On each user message, the full history is sent to POST /ai/chat.
 *  - The response is an SSE stream: text tokens accumulate into the last
 *    assistant message in real time; tool_call events are appended as actions.
 *  - The panel can be toggled open/closed from the dashboard header.
 *
 * SSE parsing:
 *  We use the native fetch() + ReadableStream API instead of EventSource because
 *  EventSource only supports GET requests with no body. For POST + auth cookie,
 *  fetch() with a text decoder is the correct approach.
 *
 * Why local state and not Zustand?
 *  Chat history is session-scoped and page-local. There is no need to share it
 *  across components, so local useState is simpler and more appropriate here.
 */

"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { X, Send, Bot, Loader2, Wrench, RotateCcw } from "lucide-react";
import { useParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { useSelectionStore } from "@/stores/useSelectionStore";
import { ChatMessage } from "@/types";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import api from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ChatSidebarProps {
  onClose: () => void;
}

export function ChatSidebar({ onClose }: ChatSidebarProps) {
  type PendingDelete = { ticket_id: string; ticket_title: string };
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I'm your AI assistant. I can help you manage tickets — create, search, update status, add comments, and reassign. What would you like to do?",
      created_at: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [deleteQueue, setDeleteQueue] = useState<PendingDelete[]>([]);
  const router = useRouter();
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Thread ID logic
  const threadIdRef = useRef<string>("");
  
  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("ai_thread_id");
      if (stored) {
        threadIdRef.current = stored;
      } else {
        const newId = crypto.randomUUID();
        threadIdRef.current = newId;
        localStorage.setItem("ai_thread_id", newId);
      }
    }
  }, []);

  const resetChat = useCallback(() => {
    const newId = crypto.randomUUID();
    threadIdRef.current = newId;
    if (typeof window !== "undefined") {
      localStorage.setItem("ai_thread_id", newId);
    }
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        content: "Session reset. How can I help you today?",
        created_at: new Date().toISOString(),
      },
    ]);
  }, []);

  const params = useParams();
  const currentTicketId = params?.id as string | undefined;
  const { selectedTicketIds } = useSelectionStore();
  const pendingDelete = deleteQueue[0] ?? null;

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    setInput("");
    setIsStreaming(true);

    // Append user message
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };

    // Placeholder for the assistant's streaming response
    const assistantId = crypto.randomUUID();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      actions: [],
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    // With persistent memory: send only the new user message + thread_id.
    // The agent recovers full conversation history from its PostgreSQL checkpoint.
    // Fallback (no checkpointer): send all messages as before.
    const historyToSend = [...messages, userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      abortRef.current = new AbortController();

      const cookieMatch = document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/);
      const authHeader = cookieMatch
        ? `Bearer ${decodeURIComponent(cookieMatch[1])}`
        : "";

      const response = await fetch(`${API_URL}/api/v1/ai/chat`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(authHeader ? { Authorization: authHeader } : {}),
        },
        body: JSON.stringify({
          messages: historyToSend,
          thread_id: threadIdRef.current,
          current_ticket_id: currentTicketId,
          selected_ticket_ids: selectedTicketIds,
        }),
        signal: abortRef.current.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`API error: ${response.status}`);
      }

      // Parse the SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by double newlines
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? ""; // Keep any incomplete event in the buffer

        for (const part of parts) {
          const line = part.replace(/^data: /, "").trim();
          if (!line) continue;

          try {
            const event = JSON.parse(line) as {
              type: string;
              content?: string;
              name?: string;
              result?: string;
              thread_id?: string;
              ticket_id?: string;
              ticket_title?: string;
            };

            if (event.type === "session" && event.thread_id) {
              // Confirm/update thread_id from server (in case it was generated server-side)
              threadIdRef.current = event.thread_id as string;
              localStorage.setItem("ai_thread_id", event.thread_id as string);
            } else if (event.type === "token" && event.content) {
              // Append text token to the assistant message
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + event.content }
                    : m
                )
              );
            } else if (event.type === "error" && event.content) {
              // Show configuration/server error in the chat
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: event.content || "Error del servidor." }
                    : m
                )
              );
            } else if (event.type === "tool_call" && event.name) {
              // Append executed action to the actions list
              const actionLabel = formatToolAction(event.name, event.result ?? "");
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, actions: [...(m.actions ?? []), actionLabel] }
                    : m
                )
              );
            } else if (event.type === "confirmation_required" && event.ticket_id) {
              // Queue delete confirmations so multiple selected tickets are confirmed one by one.
              const ticketId = event.ticket_id;
              const ticketTitle = event.ticket_title ?? "this ticket";
              setDeleteQueue((prev) => [
                ...prev,
                {
                  ticket_id: ticketId,
                  ticket_title: ticketTitle,
                },
              ]);
            } else if (event.type === "done") {
              break;
            }
          } catch {
            // Ignore malformed SSE events
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name === "AbortError") return; // User dismissed the request

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
              ? {
                ...m,
                content: `Error: No se pudo conectar con la IA (${err instanceof Error ? err.message : "Algo salió mal"}).`,
              }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
    }
  }, [input, isStreaming, messages, selectedTicketIds, currentTicketId]);

  /**
   * Executed when the user confirms deletion from the ConfirmDialog.
   * Calls the REST DELETE endpoint directly — the AI never touches this path.
   */
  const handleConfirmDelete = async () => {
    if (!pendingDelete) return;
    const { ticket_id, ticket_title } = pendingDelete;
    setDeleteQueue((prev) => prev.slice(1));
    try {
      await api.delete(`/tickets/${ticket_id}`);
      // Add a system message confirming the deletion
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `✅ Ticket "${ticket_title}" has been permanently deleted.`,
          created_at: new Date().toISOString(),
        },
      ]);
      router.refresh();
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `❌ Could not delete ticket "${ticket_title}". Please try again.`,
          created_at: new Date().toISOString(),
        },
      ]);
    }
  };

  const handleCancelDelete = () => {
    setDeleteQueue((prev) => prev.slice(1));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
    <div className="fixed bottom-4 right-4 w-[380px] h-[560px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col z-[200] animate-in slide-in-from-bottom-4 fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 rounded-t-2xl bg-gradient-to-r from-blue-600 to-blue-500">
        <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center">
          <Bot className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-semibold text-white">AI Assistant</p>
          <p className="text-[10px] text-blue-200">
            Powered by LangGraph · {selectedTicketIds.length > 0 ? `${selectedTicketIds.length} tickets selected` : "memory enabled"}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={resetChat}
            title="New Chat"
            aria-label="Nueva conversación"
            className="p-1.5 text-blue-100 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            onClick={onClose}
            aria-label="Cerrar chat"
            className="p-1.5 text-blue-100 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            {/* Avatar */}
            {msg.role === "assistant" && (
              <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-3.5 h-3.5 text-blue-600" />
              </div>
            )}

            <div className={`flex flex-col gap-1 max-w-[80%] ${msg.role === "user" ? "items-end" : "items-start"}`}>
              {/* Bubble */}
              <div
                className={`rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-tr-sm"
                    : "bg-slate-100 text-slate-800 rounded-tl-sm"
                }`}
              >
                {msg.content || (
                  <span className="flex items-center gap-1.5 text-slate-400 animate-pulse">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Thinking...
                  </span>
                )}
              </div>

                {/* Tool actions (highlighted chips) */}
                {msg.actions && msg.actions.length > 0 && (
                  <div className="flex flex-col gap-1 w-full">
                    {msg.actions.map((action, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-1.5 bg-green-50 border border-green-100 rounded-lg px-2.5 py-1.5 text-xs text-green-700 animate-in fade-in slide-in-from-left-2 duration-300 min-w-0"
                        style={{ animationDelay: `${i * 120}ms`, animationFillMode: "backwards" }}
                      >
                        <Wrench className="w-3 h-3 shrink-0" />
                        <span className="truncate">{action}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-3 py-3 border-t border-slate-100 rounded-b-2xl">
        <div className="flex gap-2 items-end">
          <textarea
            aria-label="Mensaje para el asistente"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me to manage your tickets..."
            rows={2}
            disabled={isStreaming}
            className="flex-1 resize-none border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 placeholder:text-slate-400"
          />
          <button
            onClick={sendMessage}
            disabled={isStreaming || !input.trim()}
            aria-label="Enviar mensaje"
            className="p-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-40 transition-colors shrink-0"
            title="Send (Enter)"
          >
            {isStreaming ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
        <p className="text-[10px] text-slate-400 mt-1.5 text-center">
          Press Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>

      {/* Server-enforced delete confirmation — triggered by the AI, confirmed by the human */}
      <ConfirmDialog
        open={!!pendingDelete}
        title="Delete ticket"
        description={`Are you sure you want to permanently delete "${pendingDelete?.ticket_title}"? This action cannot be undone.`}
        confirmLabel="Delete ticket"
        onConfirm={handleConfirmDelete}
        onCancel={handleCancelDelete}
      />
    </>
  );
}

/**
 * Convert a tool name + result into a human-readable action label.
 * Shown as green chips below the assistant message.
 */
function formatToolAction(toolName: string, result: string): string {
  const labels: Record<string, string> = {
    query_tickets: "Searched tickets",
    get_ticket: "Fetched ticket details",
    create_ticket: "Created a ticket",
    change_status: "Updated ticket status",
    add_comment: "Added a comment",
    reassign_ticket: "Reassigned ticket",
    update_ticket: "Updated ticket",
    delete_ticket: "Deletion requested",
    search_knowledge: "Searched knowledge base",
    ai_diagnose_ticket: "AI diagnosis generated",
  };
  const label = labels[toolName] ?? toolName;
  // Show a brief snippet of the result (first 60 chars)
  const snippet = result.length > 60 ? result.slice(0, 60) + "…" : result;
  return `${label}: ${snippet}`;
}
