/**
 * KanbanBoard — drag-and-drop ticket board using dnd-kit.
 *
 * Architecture:
 *   DndContext                  — provides drag state to all descendants
 *     KanbanColumn (× 4)       — useDroppable targets, one per status
 *       KanbanCard (× n)       — useDraggable items
 *     DragOverlay               — renders a ghost card while dragging
 *
 * Drag lifecycle:
 *   1. User picks up a card (dragStart) → active ticket stored in state.
 *   2. DragOverlay renders a visual copy of the card at the cursor.
 *   3. User drops over a column (dragEnd) → if the column is a different status,
 *      `updateTicketStatus` is called (which optimistically updates the UI and
 *      PATCHes the API in the background).
 *
 * Sensors:
 *   MouseSensor with a 5px activation distance prevents accidental drags when
 *   the user just wants to click a card. TouchSensor does the same for mobile.
 */

"use client";

import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { useState } from "react";
import { Ticket, TicketStatus } from "@/types";
import { KanbanColumn } from "./KanbanColumn";
import { KanbanCard } from "./KanbanCard";
import { useToast } from "@/hooks/use-toast";

const STATUSES: TicketStatus[] = ["open", "in_progress", "in_review", "closed"];

interface KanbanBoardProps {
  tickets: Ticket[];
  onStatusChange: (ticketId: string, newStatus: TicketStatus) => Promise<void>;
}

export function KanbanBoard({ tickets, onStatusChange }: KanbanBoardProps) {
  const [activeTicket, setActiveTicket] = useState<Ticket | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const { toast } = useToast();

  // Require 5px of movement before a drag starts — prevents accidental drags on click
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } })
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveTicket(event.active.data.current?.ticket ?? null);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    setActiveTicket(null);

    const { active, over } = event;
    if (!over) return;

    const ticketId = active.id as string;
    const newStatus = over.id as TicketStatus;
    const currentStatus = (active.data.current?.ticket as Ticket)?.status;

    if (newStatus === currentStatus || !STATUSES.includes(newStatus)) return;

    setUpdatingId(ticketId);
    try {
      await onStatusChange(ticketId, newStatus);
    } catch {
      toast({
        title: "Error al cambiar estado",
        description: "No se pudo mover el ticket. Inténtalo de nuevo.",
        variant: "destructive",
      });
    } finally {
      setUpdatingId(null);
    }
  };

  // Group tickets by status for each column
  const ticketsByStatus = STATUSES.reduce<Record<TicketStatus, Ticket[]>>(
    (acc, status) => {
      acc[status] = tickets.filter((t) => t.status === status);
      return acc;
    },
    { open: [], in_progress: [], in_review: [], closed: [] }
  );

  return (
    <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {STATUSES.map((status) => (
          <div key={status} className="min-w-[260px] flex-1">
            <KanbanColumn status={status} tickets={ticketsByStatus[status]} updatingId={updatingId} />
          </div>
        ))}
      </div>

      {/* DragOverlay renders a floating copy of the card at the cursor position.
          It lives outside the column DOM so it doesn't affect layout. */}
      <DragOverlay>
        {activeTicket && (
          <div className="rotate-1 shadow-xl">
            <KanbanCard ticket={activeTicket} />
          </div>
        )}
      </DragOverlay>
    </DndContext>
  );
}
