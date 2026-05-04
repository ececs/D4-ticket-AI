/**
 * TicketTable — paginated, filterable, sortable ticket list.
 *
 * Columns: title, status, priority, assignee, created_at, actions.
 *
 * Filtering is done server-side: each filter change updates the `filters` state
 * passed to `useTickets`, which re-fetches from the API. This keeps the dataset
 * small even when there are thousands of tickets.
 *
 * Sorting: clicking a column header updates the `sort_by`/`sort_dir` query params
 * sent to the API (allowed columns are validated server-side).
 */

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Ticket, TicketFilters, TicketPriority, TicketStatus } from "@/types";
import { Badge } from "@/components/ui/badge";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { STATUS_LABELS, PRIORITY_CONFIG, timeAgo } from "@/lib/utils";
import { ChevronUp, ChevronDown, ChevronsUpDown, Trash2, ExternalLink, CheckSquare, Square, ClipboardList, SearchX } from "lucide-react";
import { useSelectionStore } from "@/stores/useSelectionStore";

const STATUSES: TicketStatus[] = ["open", "in_progress", "in_review", "closed"];
const PRIORITIES: TicketPriority[] = ["low", "medium", "high", "critical"];

type SortField = "title" | "status" | "priority" | "created_at";
type SortDir = "asc" | "desc";

interface TicketTableProps {
  tickets: Ticket[];
  total: number;
  filters: TicketFilters;
  onFiltersChange: (filters: TicketFilters) => void;
  onDeleteTicket: (id: string) => Promise<void>;
  isLoading: boolean;
}

function SortIcon({ field, sortBy, sortDir }: { field: SortField; sortBy: SortField | undefined; sortDir: SortDir }) {
  if (sortBy !== field) return <ChevronsUpDown className="w-3.5 h-3.5 text-slate-400" />;
  return sortDir === "asc"
    ? <ChevronUp className="w-3.5 h-3.5 text-blue-600" />
    : <ChevronDown className="w-3.5 h-3.5 text-blue-600" />;
}

export function TicketTable({
  tickets,
  total,
  filters,
  onFiltersChange,
  onDeleteTicket,
  isLoading,
}: TicketTableProps) {
  const router = useRouter();
  const [sortBy, setSortBy] = useState<SortField | undefined>(undefined);
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const handleSort = (field: SortField) => {
    const newDir = sortBy === field && sortDir === "desc" ? "asc" : "desc";
    setSortBy(field);
    setSortDir(newDir);
    onFiltersChange({ ...filters, sort_by: field, sort_dir: newDir });
  };

  const { selectedTicketIds, toggleTicket, setSelection } = useSelectionStore();

  const handleSelectAll = () => {
    if (selectedTicketIds.length === tickets.length && tickets.length > 0) {
      setSelection([]);
    } else {
      setSelection(tickets.map(t => t.id));
    }
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setPendingDeleteId(id);
  };

  const handleConfirmDelete = async () => {
    const id = pendingDeleteId;
    setPendingDeleteId(null);
    if (id) {
      try {
        await onDeleteTicket(id);
      } catch {
        // deleteTicket already shows a toast and rolls back the UI on failure
      }
    }
  };

  const ColHeader = ({ field, label }: { field: SortField; label: string }) => (
    <button
      onClick={() => handleSort(field)}
      className="flex items-center gap-1 text-xs font-semibold text-slate-500 uppercase tracking-wide hover:text-slate-800 transition-colors"
    >
      {label}
      <SortIcon field={field} sortBy={sortBy} sortDir={sortDir} />
    </button>
  );

  return (
    <div className="space-y-4">
      {/* Filters row */}
      <div className="flex flex-wrap gap-3 items-center">
        {/* Search */}
        <input
          type="text"
          aria-label="Buscar tickets"
          placeholder="Search tickets..."
          value={filters.search ?? ""}
          onChange={(e) => onFiltersChange({ ...filters, search: e.target.value, page: 1 })}
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-52"
        />

        {/* Status filter */}
        <select
          aria-label="Filtrar por estado"
          value={filters.status ?? ""}
          onChange={(e) =>
            onFiltersChange({ ...filters, status: (e.target.value as TicketStatus) || undefined, page: 1 })
          }
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{STATUS_LABELS[s]}</option>
          ))}
        </select>

        {/* Priority filter */}
        <select
          aria-label="Filtrar por prioridad"
          value={filters.priority ?? ""}
          onChange={(e) =>
            onFiltersChange({ ...filters, priority: (e.target.value as TicketPriority) || undefined, page: 1 })
          }
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>{PRIORITY_CONFIG[p].label}</option>
          ))}
        </select>

        <span className="ml-auto text-sm text-slate-400">{total} ticket{total !== 1 ? "s" : ""}</span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-4 py-3 w-10">
                <button
                  onClick={handleSelectAll}
                  aria-label={selectedTicketIds.length === tickets.length && tickets.length > 0 ? "Deseleccionar todos" : "Seleccionar todos"}
                  className="text-slate-400 hover:text-blue-600 transition-colors"
                >
                  {selectedTicketIds.length === tickets.length && tickets.length > 0 
                    ? <CheckSquare className="w-4 h-4" /> 
                    : <Square className="w-4 h-4" />
                  }
                </button>
              </th>
              <th className="text-left px-4 py-3" aria-sort={sortBy === "title" ? (sortDir === "asc" ? "ascending" : "descending") : "none"}>
                <ColHeader field="title" label="Title" />
              </th>
              <th className="text-left px-4 py-3" aria-sort={sortBy === "status" ? (sortDir === "asc" ? "ascending" : "descending") : "none"}>
                <ColHeader field="status" label="Status" />
              </th>
              <th className="text-left px-4 py-3" aria-sort={sortBy === "priority" ? (sortDir === "asc" ? "ascending" : "descending") : "none"}>
                <ColHeader field="priority" label="Priority" />
              </th>
              <th className="text-left px-4 py-3 hidden md:table-cell">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Assignee</span>
              </th>
              <th className="text-left px-4 py-3 hidden lg:table-cell" aria-sort={sortBy === "created_at" ? (sortDir === "asc" ? "ascending" : "descending") : "none"}>
                <ColHeader field="created_at" label="Created" />
              </th>
              <th className="px-4 py-3" />
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100">
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-slate-400">
                  Loading tickets...
                </td>
              </tr>
            )}

            {!isLoading && tickets.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-14 text-center">
                  <div className="flex flex-col items-center gap-3">
                    {(filters.search || filters.status || filters.priority) ? (
                      <>
                        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center">
                          <SearchX className="w-6 h-6 text-slate-400" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-600">No tickets match your filters</p>
                          <p className="text-xs text-slate-400 mt-0.5">Try adjusting your search or clearing the filters</p>
                        </div>
                        <button
                          onClick={() => onFiltersChange({})}
                          className="text-xs text-blue-600 hover:text-blue-800 hover:underline transition-colors"
                        >
                          Clear all filters
                        </button>
                      </>
                    ) : (
                      <>
                        <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center">
                          <ClipboardList className="w-6 h-6 text-blue-400" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-600">All clear! No tickets yet</p>
                          <p className="text-xs text-slate-400 mt-0.5">Create your first ticket to get started</p>
                        </div>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            )}

            {!isLoading &&
              tickets.map((ticket) => (
                <tr
                  key={ticket.id}
                  onClick={() => router.push(`/tickets/${ticket.id}`)}
                  className={`hover:bg-slate-50 cursor-pointer transition-colors group ${
                    selectedTicketIds.includes(ticket.id) ? "bg-blue-50/50" : ""
                  }`}
                >
                  {/* Selection Checkbox */}
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => toggleTicket(ticket.id)}
                      aria-label={selectedTicketIds.includes(ticket.id) ? "Deseleccionar ticket" : "Seleccionar ticket"}
                      className={`${
                        selectedTicketIds.includes(ticket.id)
                          ? "text-blue-600"
                          : "text-slate-300 hover:text-slate-400"
                      } transition-colors`}
                    >
                      {selectedTicketIds.includes(ticket.id) 
                        ? <CheckSquare className="w-4 h-4" /> 
                        : <Square className="w-4 h-4" />
                      }
                    </button>
                  </td>
                  {/* Title */}
                  <td className="px-4 py-3">
                    <span className="font-medium text-slate-800 group-hover:text-blue-600 transition-colors line-clamp-1">
                      {ticket.title}
                    </span>
                    <span className="text-xs text-slate-400 font-mono ml-2">
                      #{ticket.id.slice(0, 6)}
                    </span>
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3">
                    <Badge variant={ticket.status as "open" | "in_progress" | "in_review" | "closed"}>
                      {STATUS_LABELS[ticket.status]}
                    </Badge>
                  </td>

                  {/* Priority */}
                  <td className="px-4 py-3">
                    <Badge variant={ticket.priority as "low" | "medium" | "high" | "critical"}>
                      {PRIORITY_CONFIG[ticket.priority].label}
                    </Badge>
                  </td>

                  {/* Assignee */}
                  <td className="px-4 py-3 hidden md:table-cell">
                     {ticket.assignee ? (
                      <div className="flex items-center gap-2">
                        <UserAvatar 
                          src={ticket.assignee.avatar_url} 
                          name={ticket.assignee.name} 
                          size="xs" 
                        />
                        <span className="text-slate-600 truncate max-w-[120px]">{ticket.assignee.name}</span>
                      </div>
                    ) : (
                      <span className="text-slate-400">Unassigned</span>
                    )}
                  </td>

                  {/* Created at */}
                  <td className="px-4 py-3 hidden lg:table-cell text-slate-500">
                    {timeAgo(ticket.created_at)}
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => { e.stopPropagation(); router.push(`/tickets/${ticket.id}`); }}
                        aria-label="Abrir ticket"
                        className="p-1.5 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
                        title="Open ticket"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => handleDelete(e, ticket.id)}
                        aria-label="Eliminar ticket"
                        className="p-1.5 rounded hover:bg-red-50 text-slate-400 hover:text-red-600 transition-colors"
                        title="Delete ticket"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > (filters.size ?? 20) && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => onFiltersChange({ ...filters, page: Math.max(1, (filters.page ?? 1) - 1) })}
            disabled={(filters.page ?? 1) <= 1}
            className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
          >
            Previous
          </button>
          <span className="text-sm text-slate-500">
            Page {filters.page ?? 1} of {Math.ceil(total / (filters.size ?? 20))}
          </span>
          <button
            onClick={() => onFiltersChange({ ...filters, page: (filters.page ?? 1) + 1 })}
            disabled={(filters.page ?? 1) >= Math.ceil(total / (filters.size ?? 20))}
            className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
          >
            Next
          </button>
        </div>
      )}

      <ConfirmDialog
        open={!!pendingDeleteId}
        title="Delete ticket"
        description="This action cannot be undone. The ticket and all its comments and attachments will be permanently removed."
        confirmLabel="Delete ticket"
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDeleteId(null)}
      />
    </div>
  );
}
