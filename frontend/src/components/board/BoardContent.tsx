/**
 * BoardContent — the main client component for the board page.
 *
 * Responsibilities:
 *  1. Toggle between list (TicketTable) and kanban (KanbanBoard) views.
 *  2. Hold the filter state shared between both views.
 *  3. Show the "New Ticket" button and open the TicketForm dialog.
 *  4. Connect useTickets (data fetching) to both views.
 *
 * This is a Client Component ("use client") because it needs:
 *  - useState for view toggle and filter state
 *  - dnd-kit sensors (non-serializable, cannot be passed from Server Components)
 *  - The dialog for creating new tickets
 */

"use client";

import { useState } from "react";
import { LayoutList, Kanban, Plus } from "lucide-react";
import { useTickets } from "@/hooks/useTickets";
import { useUsers } from "@/hooks/useUsers";
import { KanbanBoard } from "./KanbanBoard";
import { TicketTable } from "@/components/tickets/TicketTable";
import { TicketForm } from "@/components/tickets/TicketForm";
import { Ticket, TicketFilters, TicketStatus } from "@/types";

type ViewMode = "list" | "kanban";

export function BoardContent() {
  const [view, setView] = useState<ViewMode>("list");
  const [filters, setFilters] = useState<TicketFilters>({ page: 1, size: 20 });
  const [showForm, setShowForm] = useState(false);

  const { tickets, total, isLoading, updateTicketStatus, deleteTicket, refetch } =
    useTickets(filters);
  const { users } = useUsers();

  const handleCreateSuccess = (ticket: Ticket) => {
    refetch(); // Re-fetch after creation to pick up the server-assigned values
    void ticket; // ticket is returned by the API but we re-fetch for consistency
  };

  return (
    <div className="p-6">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Tickets</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Manage and track all work items
          </p>
        </div>

        {/* Controls: view toggle + new ticket */}
        <div className="flex items-center gap-3">
          {/* List / Kanban toggle */}
          <div className="flex items-center bg-slate-100 rounded-lg p-1 gap-0.5">
            <button
              onClick={() => setView("list")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                view === "list"
                  ? "bg-white text-slate-800 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              <LayoutList className="w-4 h-4" />
              List
            </button>
            <button
              onClick={() => setView("kanban")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                view === "kanban"
                  ? "bg-white text-slate-800 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              <Kanban className="w-4 h-4" />
              Kanban
            </button>
          </div>

          {/* New ticket button */}
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 active:bg-blue-800 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            New ticket
          </button>
        </div>
      </div>

      {/* Content area */}
      {view === "list" ? (
        <TicketTable
          tickets={tickets}
          total={total}
          filters={filters}
          onFiltersChange={setFilters}
          onDeleteTicket={deleteTicket}
          isLoading={isLoading}
        />
      ) : (
        <KanbanBoard
          tickets={tickets}
          onStatusChange={(id: string, status: TicketStatus) =>
            updateTicketStatus(id, status)
          }
        />
      )}

      {/* Create ticket dialog */}
      <TicketForm
        open={showForm}
        onClose={() => setShowForm(false)}
        onSuccess={handleCreateSuccess}
        users={users}
      />
    </div>
  );
}
