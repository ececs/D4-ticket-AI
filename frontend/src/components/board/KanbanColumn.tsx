/**
 * KanbanColumn — a droppable status column in the Kanban board.
 *
 * Uses dnd-kit's useDroppable hook. When a card is dragged over this column,
 * `isOver` becomes true and we apply a highlight ring to give visual feedback.
 *
 * Each column renders its ticket cards as KanbanCard components.
 */

"use client";

import { useDroppable } from "@dnd-kit/core";
import { Ticket, TicketStatus } from "@/types";
import { KanbanCard } from "./KanbanCard";
import { STATUS_LABELS } from "@/lib/utils";

// Column header colors keyed by status
const COLUMN_COLORS: Record<TicketStatus, string> = {
  open: "bg-blue-500",
  in_progress: "bg-amber-500",
  in_review: "bg-purple-500",
  closed: "bg-green-500",
};

interface KanbanColumnProps {
  status: TicketStatus;
  tickets: Ticket[];
  updatingId?: string | null;
}

export function KanbanColumn({ status, tickets, updatingId }: KanbanColumnProps) {
  // useDroppable: this column acts as a drop target.
  // The id must match the status value so onDragEnd can identify the target column.
  const { setNodeRef, isOver } = useDroppable({ id: status });

  return (
    <div className="flex flex-col min-w-0 flex-1">
      {/* Column header */}
      <div className="flex items-center gap-2 mb-3">
        <span className={`w-2.5 h-2.5 rounded-full ${COLUMN_COLORS[status]}`} />
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
          {STATUS_LABELS[status]}
        </h3>
        <span className="ml-auto text-xs font-medium text-slate-400 bg-slate-100 rounded-full px-2 py-0.5">
          {tickets.length}
        </span>
      </div>

      {/* Drop zone — highlighted when a card is dragged over */}
      <div
        ref={setNodeRef}
        className={`flex flex-col gap-2 flex-1 min-h-[120px] rounded-xl p-2 transition-colors ${
          isOver ? "bg-blue-50 ring-2 ring-blue-200" : "bg-slate-100"
        }`}
      >
        {tickets.map((ticket) => (
          <KanbanCard key={ticket.id} ticket={ticket} isUpdating={updatingId === ticket.id} />
        ))}

        {tickets.length === 0 && (
          <div className="flex items-center justify-center flex-1 text-sm text-slate-400 py-6">
            No tickets
          </div>
        )}
      </div>
    </div>
  );
}
