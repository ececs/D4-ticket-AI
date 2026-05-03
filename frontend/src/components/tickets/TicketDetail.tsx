/**
 * TicketDetail — full ticket view with inline editing, comments, and attachments.
 *
 * Sections:
 *  1. Header: title (inline edit), status selector, priority selector, back button
 *  2. Sidebar: assignee picker, metadata (author, created, updated)
 *  3. Description: inline edit with textarea
 *  4. Comments: list (newest last) + add-comment form
 *  5. Attachments: upload dropzone + file list with download/delete
 *
 * All edits are sent via PATCH /tickets/{id} and the local state is updated
 * immediately (optimistic) so the UI feels instant.
 */

"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft, Paperclip, Trash2, Download, MessageSquare, Send, Loader2, Sparkles,
} from "lucide-react";
import api from "@/lib/api";
import {
  Ticket, Comment, Attachment, TicketStatus, TicketPriority, User,
} from "@/types";
import { Badge } from "@/components/ui/badge";
import { STATUS_LABELS, PRIORITY_CONFIG, timeAgo, formatFileSize } from "@/lib/utils";
import { useUsers } from "@/hooks/useUsers";

const STATUSES: TicketStatus[] = ["open", "in_progress", "in_review", "closed"];
const PRIORITIES: TicketPriority[] = ["low", "medium", "high", "critical"];

interface TicketDetailProps {
  ticketId: string;
}

export function TicketDetail({ ticketId }: TicketDetailProps) {
  const router = useRouter();
  const { users } = useUsers();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inline edit state
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [editingDesc, setEditingDesc] = useState(false);
  const [descDraft, setDescDraft] = useState("");

  // Comment form state
  const [commentText, setCommentText] = useState("");
  const [isSubmittingComment, setIsSubmittingComment] = useState(false);

  // Attachment upload state
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  
  // AI Diagnosis state
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [aiDiagnosis, setAiDiagnosis] = useState<string | null>(null);

  // ── Fetch ticket, comments, attachments ──────────────────────────────────

  useEffect(() => {
    setIsLoading(true);
    Promise.all([
      api.get<Ticket>(`/tickets/${ticketId}`),
      api.get<Comment[]>(`/tickets/${ticketId}/comments`),
      api.get<Attachment[]>(`/tickets/${ticketId}/attachments`).catch(() => ({ data: [] as Attachment[] })),
    ])
      .then(([ticketRes, commentsRes, attachmentsRes]) => {
        setTicket(ticketRes.data);
        setComments(commentsRes.data);
        setAttachments(attachmentsRes.data);
      })
      .catch((err) => {
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail;
        setError(
          status === 404
            ? "Ticket not found"
            : detail
            ? `Error: ${detail}`
            : `Failed to load ticket (${status ?? "network error"})`
        );
      })
      .finally(() => setIsLoading(false));
  }, [ticketId]);

  // ── Ticket field updates ─────────────────────────────────────────────────

  const patchTicket = async (data: Partial<Ticket>) => {
    if (!ticket) return;
    const { data: updated } = await api.patch<Ticket>(`/tickets/${ticketId}`, data);
    setTicket(updated);
  };

  const handleStatusChange = (status: TicketStatus) => patchTicket({ status });
  const handlePriorityChange = (priority: TicketPriority) => patchTicket({ priority });
  const handleAssigneeChange = (assigneeId: string) =>
    patchTicket({ assignee_id: assigneeId || null } as Partial<Ticket>);

  const saveTitle = async () => {
    if (titleDraft.trim() && titleDraft !== ticket?.title) {
      await patchTicket({ title: titleDraft.trim() });
    }
    setEditingTitle(false);
  };

  const saveDesc = async () => {
    await patchTicket({ description: descDraft });
    setEditingDesc(false);
  };

  // ── Comments ─────────────────────────────────────────────────────────────

  const submitComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;
    setIsSubmittingComment(true);
    try {
      const { data: newComment } = await api.post<Comment>(
        `/tickets/${ticketId}/comments`,
        { content: commentText.trim() }
      );
      setComments((prev) => [...prev, newComment]);
      setCommentText("");
    } finally {
      setIsSubmittingComment(false);
    }
  };

  const deleteComment = async (commentId: string) => {
    if (!confirm("Delete this comment?")) return;
    await api.delete(`/tickets/${ticketId}/comments/${commentId}`);
    setComments((prev) => prev.filter((c) => c.id !== commentId));
  };

  // ── Attachments ──────────────────────────────────────────────────────────

  const uploadFile = async (file: File) => {
    setIsUploading(true);
    setUploadError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const { data: att } = await api.post<Attachment>(
        `/tickets/${ticketId}/attachments`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setAttachments((prev) => [...prev, att]);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setUploadError(axiosErr.response?.data?.detail ?? "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const deleteAttachment = async (attId: string) => {
    if (!confirm("Delete this attachment?")) return;
    await api.delete(`/tickets/${ticketId}/attachments/${attId}`);
    setAttachments((prev) => prev.filter((a) => a.id !== attId));
  };

  // ── AI Diagnosis ─────────────────────────────────────────────────────────

  const handleAIDiagnose = async () => {
    setIsDiagnosing(true);
    setAiDiagnosis(null);
    try {
      const { data } = await api.post<{ diagnosis: string }>(`/tickets/${ticketId}/ai-diagnose`);
      setAiDiagnosis(data.diagnosis);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      alert(axiosErr.response?.data?.detail ?? "Error al generar diagnóstico");
    } finally {
      setIsDiagnosing(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="p-6">
        <p className="text-red-600">{error ?? "Ticket not found"}</p>
        <button onClick={() => router.push("/board")} className="mt-2 text-blue-600 hover:underline text-sm">
          Back to board
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Back */}
      <button
        onClick={() => router.push("/board")}
        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-5 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Back to board
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-6">
        {/* ── Main column ── */}
        <div className="space-y-6">
          {/* Title */}
          <div>
            {editingTitle ? (
              <div className="flex gap-2">
                <input
                  autoFocus
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  onBlur={saveTitle}
                  onKeyDown={(e) => e.key === "Enter" && saveTitle()}
                  className="flex-1 text-2xl font-bold border-b-2 border-blue-500 outline-none bg-transparent text-slate-900"
                />
              </div>
            ) : (
              <h1
                onClick={() => { setTitleDraft(ticket.title); setEditingTitle(true); }}
                className="text-2xl font-bold text-slate-900 cursor-text hover:text-blue-600 transition-colors"
                title="Click to edit"
              >
                {ticket.title}
              </h1>
            )}

            {/* Status + priority row */}
            <div className="flex items-center gap-3 mt-3">
              <select
                value={ticket.status}
                onChange={(e) => handleStatusChange(e.target.value as TicketStatus)}
                className="text-sm border border-slate-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                ))}
              </select>

              <select
                value={ticket.priority}
                onChange={(e) => handlePriorityChange(e.target.value as TicketPriority)}
                className="text-sm border border-slate-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>{PRIORITY_CONFIG[p].label}</option>
                ))}
              </select>

              <Badge variant={ticket.status}>
                {STATUS_LABELS[ticket.status]}
              </Badge>

              {/* AI Diagnosis Button */}
              <button
                onClick={handleAIDiagnose}
                disabled={isDiagnosing}
                className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-700 hover:to-indigo-700 transition-all shadow-sm disabled:opacity-50"
              >
                {isDiagnosing ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5" />
                )}
                Diagnóstico IA
              </button>
            </div>
          </div>

          {/* AI Diagnosis Results */}
          {aiDiagnosis && (
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded-xl p-4 shadow-sm relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-2">
                <Sparkles className="w-4 h-4 text-blue-400 opacity-20 group-hover:opacity-100 transition-opacity" />
              </div>
              <h3 className="text-xs font-bold text-blue-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                Análisis Técnico IA
              </h3>
              <p className="text-sm text-slate-700 leading-relaxed italic whitespace-pre-wrap">
                {aiDiagnosis}
              </p>
              <div className="mt-3 flex justify-end">
                <button 
                  onClick={() => setAiDiagnosis(null)}
                  className="text-[10px] text-blue-400 hover:text-blue-600 font-medium"
                >
                  Cerrar análisis
                </button>
              </div>
            </div>
          )}

          {/* Description */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <h2 className="text-sm font-semibold text-slate-700 mb-2">Description</h2>
            {editingDesc ? (
              <div className="space-y-2">
                <textarea
                  autoFocus
                  value={descDraft}
                  onChange={(e) => setDescDraft(e.target.value)}
                  rows={4}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
                <div className="flex gap-2">
                  <button onClick={saveDesc} className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                    Save
                  </button>
                  <button onClick={() => setEditingDesc(false)} className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <p
                onClick={() => { setDescDraft(ticket.description ?? ""); setEditingDesc(true); }}
                className="text-sm text-slate-600 whitespace-pre-wrap cursor-text hover:bg-slate-50 rounded-lg p-2 -m-2 transition-colors min-h-[60px]"
                title="Click to edit"
              >
                {ticket.description || <span className="text-slate-400 italic">No description. Click to add one.</span>}
              </p>
            )}
          </div>

          {/* Attachments */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
                <Paperclip className="w-4 h-4" /> Attachments ({attachments.length})
              </h2>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50 transition-colors"
              >
                {isUploading ? "Uploading..." : "Upload file"}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
              />
            </div>

            {uploadError && (
              <p className="text-xs text-red-600 mb-2">{uploadError}</p>
            )}

            {attachments.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-4">No attachments yet</p>
            ) : (
              <ul className="space-y-2">
                {attachments.map((att) => (
                  <li key={att.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-50 group">
                    <Paperclip className="w-4 h-4 text-slate-400 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-700 truncate">{att.filename}</p>
                      <p className="text-xs text-slate-400">{formatFileSize(att.size_bytes)}</p>
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {att.download_url && (
                        <a
                          href={att.download_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1.5 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
                          title="Download"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </a>
                      )}
                      <button
                        onClick={() => deleteAttachment(att.id)}
                        className="p-1.5 rounded hover:bg-red-50 text-slate-400 hover:text-red-600 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Comments */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-1.5">
              <MessageSquare className="w-4 h-4" /> Comments ({comments.length})
            </h2>

            {/* Comment list */}
            <div className="space-y-4 mb-4">
              {comments.length === 0 && (
                <p className="text-sm text-slate-400 text-center py-2">No comments yet. Be the first!</p>
              )}
              {comments.map((c) => (
                <div key={c.id} className="flex gap-3 group">
                  {c.author?.avatar_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={c.author.avatar_url} alt={c.author.name} className="w-7 h-7 rounded-full shrink-0 mt-0.5" />
                  ) : (
                    <span className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center text-xs font-medium text-slate-600 shrink-0 mt-0.5">
                      {c.author?.name.charAt(0).toUpperCase() ?? "?"}
                    </span>
                  )}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold text-slate-700">{c.author?.name ?? "Unknown"}</span>
                      <span className="text-xs text-slate-400">{timeAgo(c.created_at)}</span>
                    </div>
                    <p className="text-sm text-slate-600 whitespace-pre-wrap">{c.content}</p>
                  </div>
                  <button
                    onClick={() => deleteComment(c.id)}
                    className="p-1.5 rounded hover:bg-red-50 text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all self-start mt-0.5"
                    title="Delete comment"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>

            {/* Add comment form */}
            <form onSubmit={submitComment} className="flex gap-2">
              <textarea
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder="Add a comment..."
                rows={2}
                className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submitComment(e as unknown as React.FormEvent);
                }}
              />
              <button
                type="submit"
                disabled={isSubmittingComment || !commentText.trim()}
                className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors self-end"
                title="Send (Ctrl+Enter)"
              >
                {isSubmittingComment ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </form>
          </div>
        </div>

        {/* ── Sidebar ── */}
        <aside className="space-y-4">
          {/* Assignee */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Assignee</h3>
            <select
              value={ticket.assignee_id ?? ""}
              onChange={(e) => handleAssigneeChange(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Unassigned</option>
              {users.map((u: User) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>

            {ticket.assignee && (
              <div className="flex items-center gap-2 mt-3">
                {ticket.assignee.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={ticket.assignee.avatar_url} alt={ticket.assignee.name} className="w-7 h-7 rounded-full" />
                ) : (
                  <span className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center text-xs font-medium text-slate-600">
                    {ticket.assignee.name.charAt(0).toUpperCase()}
                  </span>
                )}
                <div>
                  <p className="text-sm font-medium text-slate-700">{ticket.assignee.name}</p>
                  <p className="text-xs text-slate-400">{ticket.assignee.email}</p>
                </div>
              </div>
            )}
          </div>

          {/* Metadata */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Details</h3>

            <div>
              <p className="text-xs text-slate-400">Author</p>
              <p className="text-sm text-slate-700">{ticket.author?.name ?? "Unknown"}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Created</p>
              <p className="text-sm text-slate-700">{timeAgo(ticket.created_at)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Last updated</p>
              <p className="text-sm text-slate-700">{timeAgo(ticket.updated_at)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Ticket ID</p>
              <p className="text-xs text-slate-500 font-mono">{ticket.id}</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
