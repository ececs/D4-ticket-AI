import { Ticket, TicketFilters, TicketPriority, TicketStatus } from "@/types";

const PRIORITY_ORDER: Record<TicketPriority, number> = {
  low: 0,
  medium: 1,
  high: 2,
  critical: 3,
};

const STATUS_ORDER: Record<TicketStatus, number> = {
  open: 0,
  in_progress: 1,
  in_review: 2,
  closed: 3,
};

type SortField = "title" | "status" | "priority" | "created_at";
type SortDir = "asc" | "desc";

export interface TicketInsertResult {
  tickets: Ticket[];
  totalDelta: number;
  needsRefetch: boolean;
}

function matchesNonSearchFilters(ticket: Ticket, filters: TicketFilters): boolean {
  if (filters.status && ticket.status !== filters.status) return false;
  if (filters.priority && ticket.priority !== filters.priority) return false;
  if (filters.assignee_id && ticket.assignee_id !== filters.assignee_id) return false;
  return true;
}

function compareTickets(a: Ticket, b: Ticket, sortBy: SortField, order: SortDir): number {
  let base = 0;

  switch (sortBy) {
    case "title":
      base = a.title.localeCompare(b.title, undefined, { sensitivity: "base" });
      break;
    case "status":
      base = STATUS_ORDER[a.status] - STATUS_ORDER[b.status];
      break;
    case "priority":
      base = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
      break;
    case "created_at":
    default:
      base = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      break;
  }

  return order === "asc" ? base : -base;
}

export function integrateCreatedTicket(
  prev: Ticket[],
  created: Ticket,
  filters: TicketFilters,
): TicketInsertResult {
  if (prev.some((ticket) => ticket.id === created.id)) {
    return {
      tickets: prev.map((ticket) => (ticket.id === created.id ? created : ticket)),
      totalDelta: 0,
      needsRefetch: false,
    };
  }

  if (filters.search) {
    return { tickets: prev, totalDelta: 0, needsRefetch: true };
  }

  if (!matchesNonSearchFilters(created, filters)) {
    return { tickets: prev, totalDelta: 0, needsRefetch: false };
  }

  const page = filters.page ?? 1;
  if (page > 1) {
    return { tickets: prev, totalDelta: 0, needsRefetch: true };
  }

  const sortBy = (filters.sort_by as SortField | undefined) ?? "created_at";
  const order = filters.order ?? "desc";
  const next = [...prev, created].sort((a, b) => compareTickets(a, b, sortBy, order));
  const size = filters.size;
  const limited = typeof size === "number" && size > 0 ? next.slice(0, size) : next;

  return {
    tickets: limited,
    totalDelta: 1,
    needsRefetch: false,
  };
}
