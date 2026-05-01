/**
 * KanbanCard — a single draggable ticket card in the Kanban view.
 *
 * Uses dnd-kit's useDraggable hook. While dragging, the card becomes
 * semi-transparent and a drag overlay is rendered by KanbanBoard.
 *
 * Clicking the card (without dragging) navigates to the ticket detail page.
 */

"use client";

import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { useRouter } from "next/navigation";
import { Ticket } from "@/types";
import { Badge } from "@/components/ui/badge";
import { PRIORITY_CONFIG } from "@/lib/utils";

interface KanbanCardProps {
  ticket: Ticket;
}

export function KanbanCard({ ticket }: KanbanCardProps) {
  const router = useRouter();

  // useDraggable returns refs and transform values.
  // We set the data payload so KanbanBoard's onDragEnd knows which ticket moved.
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: ticket.id,
    data: { ticket },
  });

  const style = {
    transform: CSS.Translate.toString(transform),
    // Reduce opacity while dragging — the DragOverlay renders a ghost in full opacity
    opacity: isDragging ? 0.4 : 1,
  };

  const priorityCfg = PRIORITY_CONFIG[ticket.priority];

  const handleClick = () => {
    if (!isDragging) {
      router.push(`/tickets/${ticket.id}`);
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={handleClick}
      className="bg-white rounded-lg border border-slate-200 p-3 shadow-sm cursor-grab active:cursor-grabbing hover:border-slate-300 hover:shadow-md transition-all group"
    >
      {/* Priority badge */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${priorityCfg.color}`}>
          {priorityCfg.label}
        </span>
        <span className="text-xs text-slate-400 font-mono shrink-0">
          #{ticket.id.slice(0, 6)}
        </span>
      </div>

      {/* Title */}
      <p className="text-sm font-medium text-slate-800 leading-snug mb-3 group-hover:text-blue-600 transition-colors line-clamp-2">
        {ticket.title}
      </p>

      {/* Assignee */}
      {ticket.assignee && (
        <div className="flex items-center gap-1.5">
          {ticket.assignee.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={ticket.assignee.avatar_url}
              alt={ticket.assignee.name}
              className="w-5 h-5 rounded-full"
            />
          ) : (
            <span className="w-5 h-5 rounded-full bg-slate-200 flex items-center justify-center text-xs font-medium text-slate-600">
              {ticket.assignee.name.charAt(0).toUpperCase()}
            </span>
          )}
          <span className="text-xs text-slate-500 truncate">{ticket.assignee.name}</span>
        </div>
      )}
    </div>
  );
}
