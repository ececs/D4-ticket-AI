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
    <div className="px-3 py-4 sm:p-6">
      {/* Page header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 sm:text-2xl">Tickets</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Manage and track all work items
          </p>
        </div>

        {/* Controls: view toggle + new ticket */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          {/* Page size selector */}
          <select
            aria-label="Tickets per page"
            value={filters.size ?? 20}
            onChange={(e) =>
              setFilters({ ...filters, size: Number(e.target.value), page: 1 })
            }
            className="w-full border border-slate-200 rounded-lg px-2 py-1.5 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 sm:w-auto"
          >
            {[20, 50, 100].map((n) => (
              <option key={n} value={n}>{n} per page</option>
            ))}
          </select>

          {/* List / Kanban toggle */}
          <div className="flex items-center rounded-lg bg-slate-100 p-1 gap-0.5">
            <button
              onClick={() => setView("list")}
              className={`flex flex-1 items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all sm:flex-none ${
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
              className={`flex flex-1 items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all sm:flex-none ${
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
            className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 active:bg-blue-800 sm:w-auto"
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
          users={users}
        />
      ) : (
        <>
          <KanbanBoard
            tickets={tickets}
            onStatusChange={(id: string, status: TicketStatus) =>
              updateTicketStatus(id, status)
            }
          />
          {total > (filters.size ?? 20) && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <button
                onClick={() =>
                  setFilters({ ...filters, page: Math.max(1, (filters.page ?? 1) - 1) })
                }
                disabled={(filters.page ?? 1) <= 1}
                className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
              >
                Previous
              </button>
              <span className="text-sm text-slate-500">
                Page {filters.page ?? 1} of {Math.ceil(total / (filters.size ?? 20))}
              </span>
              <button
                onClick={() =>
                  setFilters({ ...filters, page: (filters.page ?? 1) + 1 })
                }
                disabled={(filters.page ?? 1) >= Math.ceil(total / (filters.size ?? 20))}
                className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </>
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
