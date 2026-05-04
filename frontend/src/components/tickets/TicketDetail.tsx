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
  ArrowLeft, Clock, Paperclip, Trash2, Download, MessageSquare, Send, Loader2, Sparkles, RefreshCw, Globe, ExternalLink, Info, ChevronDown, ChevronUp,
} from "lucide-react";
import api from "@/lib/api";
import {
  Ticket, Comment, Attachment, TicketStatus, TicketPriority, User,
} from "@/types";
import { getAuthToken } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { STATUS_LABELS, PRIORITY_CONFIG, timeAgo, formatFileSize } from "@/lib/utils";
import { useUsers } from "@/hooks/useUsers";
import { UserAvatar } from "@/components/ui/UserAvatar";
import useNotificationStore from "@/stores/notificationStore";

const STATUSES: TicketStatus[] = ["open", "in_progress", "in_review", "closed"];
const PRIORITIES: TicketPriority[] = ["low", "medium", "high", "critical"];

interface TicketDetailProps {
  ticketId: string;
}

export function TicketDetail({ ticketId }: TicketDetailProps) {
  const router = useRouter();
  const { users } = useUsers();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { refreshSignal, lastTicketId } = useNotificationStore();
  const { toast } = useToast();

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
  const [editingUrl, setEditingUrl] = useState(false);
  const [urlDraft, setUrlDraft] = useState("");
  const [editingSummary, setEditingSummary] = useState(false);
  const [summaryDraft, setSummaryDraft] = useState("");

  // Comment form state
  const [commentText, setCommentText] = useState("");
  const [isSubmittingComment, setIsSubmittingComment] = useState(false);

  // Attachment upload state
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  
  // AI Diagnosis state
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [aiDiagnosis, setAiDiagnosis] = useState<string | null>(null);
  const [showDiagnosis, setShowDiagnosis] = useState(false);
  const [showExtracted, setShowExtracted] = useState(false);
  const [extractedContent, setExtractedContent] = useState<string | null>(null);
  const [isRefreshingWeb, setIsRefreshingWeb] = useState(false);


  const refreshWebContext = async () => {
    if (!ticket?.client_url) return;
    
    setIsRefreshingWeb(true);
    try {
      await api.post(`/tickets/${ticketId}/web-scrape-refresh`);
      // We don't call fetchData here because the WebSocket will trigger it
      // once the background scraping task is done.
    } catch (err) {
      console.error("Failed to trigger scrape refresh", err);
      setIsRefreshingWeb(false);
    }
  };

  // ── Fetch ticket, comments, attachments ──────────────────────────────────

  useEffect(() => {
    fetchData();
  }, [ticketId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Real-time refresh listener (WebSockets)
  useEffect(() => {
    if (refreshSignal > 0 && lastTicketId === ticketId) {
      fetchData(true);
      setIsRefreshingWeb(false);
    }
  }, [refreshSignal, lastTicketId, ticketId]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = async (background = false) => {
    if (!background) setIsLoading(true);
    try {
      const [ticketRes, commentsRes, attachmentsRes, webCtxRes] = await Promise.all([
        api.get<Ticket>(`/tickets/${ticketId}`),
        api.get<Comment[]>(`/tickets/${ticketId}/comments`),
        api.get<Attachment[]>(`/tickets/${ticketId}/attachments`).catch(() => ({ data: [] as Attachment[] })),
        api.get<{ content: string | null }>(`/tickets/${ticketId}/web-context`).catch(() => ({ data: { content: null } })),
      ]);
      setTicket(ticketRes.data);
      setComments(commentsRes.data);
      setAttachments(attachmentsRes.data);
      setExtractedContent(webCtxRes.data.content);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number; data?: { detail?: string } } })?.response?.status;
      const detail = (err as { response?: { status?: number; data?: { detail?: string } } })?.response?.data?.detail;
      setError(
        status === 404
          ? "Ticket not found"
          : detail
          ? `Error: ${detail}`
          : `Failed to load ticket (${status ?? "network error"})`
      );
    } finally {
      if (!background) setIsLoading(false);
    }
  };

  // ── Ticket field updates ─────────────────────────────────────────────────

  const patchTicket = async (data: Partial<Ticket>) => {
    if (!ticket) return;

    // Optimistic Update: update UI immediately
    const previousTicket = { ...ticket };
    setTicket({ ...ticket, ...data } as Ticket);

    try {
      const { data: updated } = await api.patch<Ticket>(`/tickets/${ticketId}`, data);
      setTicket(updated);
      toast({ title: "Cambios guardados", description: "El ticket se ha actualizado correctamente." });
    } catch (error) {
      console.error("Failed to patch ticket", error);
      setTicket(previousTicket);
      toast({ title: "Error al guardar", description: "No se pudieron guardar los cambios. Inténtalo de nuevo.", variant: "destructive" });
    }
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

  const saveUrl = async () => {
    if (urlDraft !== ticket?.client_url) {
      await patchTicket({ client_url: urlDraft.trim() || null });
    }
    setEditingUrl(false);
  };

  const saveSummary = async () => {
    if (summaryDraft !== ticket?.client_summary) {
      await patchTicket({ client_summary: summaryDraft.trim() || null });
    }
    setEditingSummary(false);
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
      toast({ title: "Comentario enviado" });
    } catch {
      toast({ title: "Error al enviar comentario", variant: "destructive" });
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
  
  const handleAIDiagnose = async (force = false) => {
    // If we already have a diagnosis and we're not forcing a refresh, just toggle visibility
    if (aiDiagnosis && !force) {
      setShowDiagnosis(!showDiagnosis);
      return;
    }

    setIsDiagnosing(true);
    setAiDiagnosis(""); // Initialize as empty string for streaming
    setShowDiagnosis(true);
    
    try {
      const token = getAuthToken();
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/tickets/${ticketId}/diagnosis`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        }
      });

      if (!response.ok) throw new Error("Failed to connect to AI service");

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      
      if (!reader) throw new Error("ReadableStream not supported");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        setAiDiagnosis((prev) => (prev || "") + chunk);
      }
    } catch (err: unknown) {
      console.error("AI Diagnosis failed", err);
      setAiDiagnosis("*(Error: No se pudo conectar con el servicio de IA para el diagnóstico en tiempo real)*");
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
                  aria-label="Título del ticket"
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
                aria-label="Estado del ticket"
                value={ticket.status}
                onChange={(e) => handleStatusChange(e.target.value as TicketStatus)}
                className="text-sm border border-slate-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                ))}
              </select>

              <select
                aria-label="Prioridad del ticket"
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
                onClick={() => handleAIDiagnose()}
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
          {aiDiagnosis && showDiagnosis && (
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded-xl p-4 shadow-sm relative overflow-hidden group animate-in fade-in slide-in-from-top-2 duration-300">
              <div className="absolute top-0 right-0 p-2 flex gap-2">
                <button
                  onClick={() => handleAIDiagnose(true)}
                  disabled={isDiagnosing}
                  aria-label="Regenerar diagnóstico"
                  className="p-1 rounded hover:bg-blue-100 text-blue-400 hover:text-blue-600 transition-colors"
                  title="Regenerar diagnóstico"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isDiagnosing ? "animate-spin" : ""}`} />
                </button>
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
                  onClick={() => setShowDiagnosis(false)}
                  className="text-[10px] text-blue-400 hover:text-blue-600 font-medium"
                >
                  Cerrar análisis
                </button>
              </div>
            </div>
          )}

          {/* Client URL Context */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
                <Globe className="w-4 h-4 text-blue-500" /> Web del Cliente
              </h2>
              <div className="flex items-center gap-3">
                {ticket.client_url && (
                  <button
                    onClick={refreshWebContext}
                    disabled={isRefreshingWeb}
                    aria-label="Actualizar análisis web"
                    className={`p-1 rounded-full hover:bg-slate-100 transition-colors ${isRefreshingWeb ? "text-blue-500" : "text-slate-400"}`}
                    title="Actualizar análisis de la web"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isRefreshingWeb ? "animate-spin" : ""}`} />
                  </button>
                )}
                {ticket.client_url && !editingUrl && (
                  <a 
                    href={ticket.client_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1"
                  >
                    Visitar <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>
            
            {editingUrl ? (
              <div className="flex gap-2">
                <input
                  autoFocus
                  aria-label="URL del cliente"
                  value={urlDraft}
                  onChange={(e) => setUrlDraft(e.target.value)}
                  placeholder="https://example.com"
                  className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button 
                  onClick={saveUrl}
                  className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  OK
                </button>
                <button 
                  onClick={() => setEditingUrl(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  X
                </button>
              </div>
            ) : (
              <p 
                onClick={() => { setUrlDraft(ticket.client_url ?? ""); setEditingUrl(true); }}
                className="text-sm text-slate-600 cursor-text hover:bg-slate-50 rounded-lg p-2 -m-2 transition-colors flex items-center gap-2"
                title="Click para editar URL"
              >
                {ticket.client_url ? (
                  <span className="truncate">{ticket.client_url}</span>
                ) : (
                  <span className="text-slate-400 italic">No hay web vinculada. Haz clic para añadir una.</span>
                )}
              </p>
            )}
            {ticket.client_url && (
              <p className="text-[10px] text-slate-400 mt-2">
                La IA usa esta web para enriquecer el diagnóstico técnico.
              </p>
            )}

            {/* AI Extracted Context Collapsible */}
            {ticket.client_url && extractedContent && (
              <div className="mt-3 border border-blue-100 bg-blue-50/30 rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowExtracted(!showExtracted)}
                  className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-medium text-blue-700 hover:bg-blue-50 transition-colors"
                >
                  <span className="flex items-center gap-1.5">
                    <Sparkles className="w-3 h-3" />
                    Análisis automático de {new URL(ticket.client_url).hostname}
                  </span>
                  {showExtracted ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>
                
                {showExtracted && (
                  <div className="px-3 pb-3 pt-1 text-[11px] text-slate-600 leading-relaxed italic border-t border-blue-100 animate-in slide-in-from-top-2">
                    {extractedContent}
                    <div className="mt-2 text-[9px] text-blue-500 font-semibold uppercase tracking-wider">
                      Contexto extraído por la IA
                    </div>
                  </div>
                )}
              </div>
            )}
            
            {ticket.client_url && !extractedContent && (
              <div className="mt-2 text-[9px] text-slate-400 italic flex items-center gap-1 px-1">
                <Clock className="w-2.5 h-2.5" /> 
                Análisis automático pendiente o en curso...
              </div>
            )}
          </div>

          {/* Client Summary Context */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <h2 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-1.5">
              <Info className="w-4 h-4 text-indigo-500" /> Perfil del Cliente
            </h2>
            
            {editingSummary ? (
              <div className="space-y-2">
                <textarea
                  autoFocus
                  value={summaryDraft}
                  onChange={(e) => setSummaryDraft(e.target.value)}
                  placeholder="Describe al cliente, tecnologías, importancia..."
                  rows={3}
                  className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
                <div className="flex gap-2">
                  <button 
                    onClick={saveSummary}
                    className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    Guardar
                  </button>
                  <button 
                    onClick={() => setEditingSummary(false)}
                    className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            ) : (
              <p 
                onClick={() => { setSummaryDraft(ticket.client_summary ?? ""); setEditingSummary(true); }}
                className="text-sm text-slate-600 cursor-text hover:bg-slate-50 rounded-lg p-2 -m-2 transition-colors min-h-[40px]"
                title="Click para editar resumen"
              >
                {ticket.client_summary ? (
                  ticket.client_summary
                ) : (
                  <span className="text-slate-400 italic">Sin resumen manual. Haz clic para añadir notas sobre el cliente.</span>
                )}
              </p>
            )}
          </div>

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
                          aria-label={`Descargar ${att.filename}`}
                          className="p-1.5 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
                          title="Download"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </a>
                      )}
                      <button
                        onClick={() => deleteAttachment(att.id)}
                        aria-label={`Eliminar ${att.filename}`}
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
                  <UserAvatar
                    src={c.author?.avatar_url}
                    name={c.author?.name ?? "?"}
                    size="sm"
                    className="mt-0.5"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold text-slate-700">{c.author?.name ?? "Unknown"}</span>
                      <span className="text-xs text-slate-400">{timeAgo(c.created_at)}</span>
                    </div>
                    <p className="text-sm text-slate-600 whitespace-pre-wrap">{c.content}</p>
                  </div>
                  <button
                    onClick={() => deleteComment(c.id)}
                    aria-label="Eliminar comentario"
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
                aria-label="Escribir un comentario"
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
                aria-label="Enviar comentario"
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
                <UserAvatar 
                  src={ticket.assignee.avatar_url} 
                  name={ticket.assignee.name} 
                  size="sm" 
                />
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
