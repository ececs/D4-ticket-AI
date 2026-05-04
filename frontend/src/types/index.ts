/**
 * Shared TypeScript types for the D4-Ticket AI frontend.
 *
 * These mirror the Pydantic schemas from the FastAPI backend.
 * Keeping them in one place makes it easy to update when the API changes.
 */

// ─── User ────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  created_at: string; // ISO 8601 string from the API
}

// ─── Ticket ──────────────────────────────────────────────────────────────────

export type TicketStatus = "open" | "in_progress" | "in_review" | "closed";
export type TicketPriority = "low" | "medium" | "high" | "critical";

export interface Ticket {
  id: string;
  title: string;
  description: string | null;
  status: TicketStatus;
  priority: TicketPriority;
  author_id: string;
  assignee_id: string | null;
  client_url: string | null;
  client_summary: string | null;
  created_at: string;
  updated_at: string;
  author: User | null;
  assignee: User | null;
}

export interface TicketListResponse {
  items: Ticket[];
  total: number;
  page: number;
  size: number;
}

export interface TicketCreate {
  title: string;
  description?: string;
  priority?: TicketPriority;
  assignee_id?: string | null;
  client_url?: string | null;
  client_summary?: string | null;
}

export interface TicketUpdate {
  title?: string;
  description?: string;
  status?: TicketStatus;
  priority?: TicketPriority;
  assignee_id?: string | null;
  client_url?: string | null;
  client_summary?: string | null;
}

// ─── Comment ─────────────────────────────────────────────────────────────────

export interface Comment {
  id: string;
  ticket_id: string;
  author_id: string;
  content: string;
  created_at: string;
  author: User | null;
}

// ─── Attachment ──────────────────────────────────────────────────────────────

export interface Attachment {
  id: string;
  ticket_id: string;
  uploader_id: string;
  filename: string;
  size_bytes: number;
  mime_type: string;
  created_at: string;
  download_url: string | null;
}

// ─── Notification ────────────────────────────────────────────────────────────

export type NotificationType =
  | "assigned"
  | "commented"
  | "status_changed"
  | "ticket_updated"
  | "ticket_deleted";

export interface Notification {
  id: string;
  user_id: string;
  type: NotificationType;
  ticket_id: string | null;
  message: string;
  read: boolean;
  created_at: string;
}

// ─── AI Chat ─────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions?: string[]; // Actions the AI performed (e.g., "Changed ticket #1 status to closed")
  created_at: string;
}

// ─── Ticket History ──────────────────────────────────────────────────────────

export interface TicketHistory {
  id: string;
  ticket_id: string | null;
  actor: User | null;
  field: string;
  old_value: string | null;
  new_value: string | null;
  created_at: string;
}

// ─── Filters ─────────────────────────────────────────────────────────────────

export interface TicketFilters {
  status?: TicketStatus;
  priority?: TicketPriority;
  assignee_id?: string;
  search?: string;
  page?: number;
  size?: number;
  sort_by?: string;
  order?: "asc" | "desc";
}
