/**
 * useTickets — data fetching hook for the tickets list.
 *
 * Manages:
 *  - Fetching the paginated ticket list from the API with filters applied.
 *  - Optimistic status updates: when the user drags a card in the Kanban,
 *    the UI updates immediately while the PATCH request is in flight.
 *    If the request fails, the previous state is restored.
 *  - Loading and error states for UI feedback.
 *
 * Why not React Query / SWR?
 *   For this scope, a simple useState + useEffect is sufficient and avoids
 *   adding another dependency. The pattern is easy to explain in an interview.
 *   In a larger app, React Query would add caching, background refetch, etc.
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { Ticket, TicketFilters, TicketListResponse, TicketStatus, TicketUpdate } from "@/types";

interface UseTicketsReturn {
  tickets: Ticket[];
  total: number;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
  updateTicketStatus: (ticketId: string, newStatus: TicketStatus) => Promise<void>;
  updateTicket: (ticketId: string, data: TicketUpdate) => Promise<Ticket>;
  deleteTicket: (ticketId: string) => Promise<void>;
}

export function useTickets(filters: TicketFilters = {}): UseTicketsReturn {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fetchKey, setFetchKey] = useState(0); // increment to trigger re-fetch

  const refetch = useCallback(() => setFetchKey((k) => k + 1), []);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    // Build query params from filters, omitting undefined/null values
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v !== undefined && v !== null && v !== "")
    );

    api.get<TicketListResponse>("/tickets", { params })
      .then(({ data }) => {
        if (!cancelled) {
          setTickets(data.items);
          setTotal(data.total);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.response?.data?.detail ?? "Failed to load tickets");
          setIsLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [fetchKey, JSON.stringify(filters)]); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Optimistically update a ticket's status in the local list, then PATCH the API.
   * If the API call fails, the original status is restored.
   */
  const updateTicketStatus = useCallback(async (ticketId: string, newStatus: TicketStatus) => {
    // Optimistic update: change the status in the local state immediately
    const previous = tickets.find((t) => t.id === ticketId);
    setTickets((prev) =>
      prev.map((t) => (t.id === ticketId ? { ...t, status: newStatus } : t))
    );

    try {
      await api.patch(`/tickets/${ticketId}`, { status: newStatus });
    } catch {
      // Rollback on failure
      if (previous) {
        setTickets((prev) =>
          prev.map((t) => (t.id === ticketId ? { ...t, status: previous.status } : t))
        );
      }
    }
  }, [tickets]);

  /**
   * Update any ticket fields and refresh the local list.
   */
  const updateTicket = useCallback(async (ticketId: string, data: TicketUpdate): Promise<Ticket> => {
    const { data: updated } = await api.patch<Ticket>(`/tickets/${ticketId}`, data);
    setTickets((prev) =>
      prev.map((t) => (t.id === ticketId ? updated : t))
    );
    return updated;
  }, []);

  /**
   * Delete a ticket and remove it from the local list.
   */
  const deleteTicket = useCallback(async (ticketId: string) => {
    await api.delete(`/tickets/${ticketId}`);
    setTickets((prev) => prev.filter((t) => t.id !== ticketId));
    setTotal((n) => n - 1);
  }, []);

  return { tickets, total, isLoading, error, refetch, updateTicketStatus, updateTicket, deleteTicket };
}
