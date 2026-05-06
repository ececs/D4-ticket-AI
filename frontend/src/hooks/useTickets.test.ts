import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import useNotificationStore from "@/stores/notificationStore";
import { useTickets } from "@/hooks/useTickets";
import { makeTicket } from "@/test/factories";

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

describe("useTickets", () => {
  beforeEach(() => {
    useNotificationStore.setState({
      notifications: [],
      unreadCount: 0,
      refreshSignal: 0,
      lastTicketId: null,
      deletedTicketId: null,
    });
    vi.clearAllMocks();
  });

  it("loads tickets on mount", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [makeTicket({ id: "ticket-1" })],
        total: 1,
        page: 1,
        size: 20,
      },
    });

    const { result } = renderHook(() => useTickets());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.tickets).toHaveLength(1);
    expect(result.current.total).toBe(1);
    expect(result.current.error).toBeNull();
  });

  it("removes a deleted ticket via realtime fast path", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [makeTicket({ id: "ticket-1" }), makeTicket({ id: "ticket-2" })],
        total: 2,
        page: 1,
        size: 20,
      },
    });

    const { result } = renderHook(() => useTickets());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      useNotificationStore.getState().triggerDelete("ticket-1");
    });

    await waitFor(() => expect(result.current.tickets.map((ticket) => ticket.id)).toEqual(["ticket-2"]));
    expect(result.current.total).toBe(1);
  });

  it("merges a partial realtime update for an existing ticket", async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({
        data: {
          items: [makeTicket({ id: "ticket-1", title: "Old" })],
          total: 1,
          page: 1,
          size: 20,
        },
      })
      .mockResolvedValueOnce({
        data: makeTicket({ id: "ticket-1", title: "Updated" }),
      });

    const { result } = renderHook(() => useTickets());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      useNotificationStore.getState().triggerRefresh("ticket-1");
    });

    await waitFor(() => expect(result.current.tickets[0].title).toBe("Updated"));
  });

  it("falls back to a full refetch when search filters make local insertion unsafe", async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({
        data: {
          items: [makeTicket({ id: "ticket-1", title: "Old" })],
          total: 1,
          page: 1,
          size: 20,
        },
      })
      .mockResolvedValueOnce({
        data: makeTicket({ id: "ticket-2", title: "Login bug" }),
      })
      .mockResolvedValueOnce({
        data: {
          items: [makeTicket({ id: "ticket-1", title: "Old" }), makeTicket({ id: "ticket-2", title: "Login bug" })],
          total: 2,
          page: 1,
          size: 20,
        },
      });

    const { result } = renderHook(() => useTickets({ search: "login" }));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      useNotificationStore.getState().triggerRefresh("ticket-2");
    });

    await waitFor(() => expect(result.current.total).toBe(2));
    expect(result.current.tickets.map((ticket) => ticket.id)).toEqual(["ticket-1", "ticket-2"]);
    expect(vi.mocked(api.get)).toHaveBeenCalledWith("/tickets/ticket-2");
  });

  it("rolls back optimistic status changes when patch fails", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [makeTicket({ id: "ticket-1", status: "open" })],
        total: 1,
        page: 1,
        size: 20,
      },
    });
    vi.mocked(api.patch).mockRejectedValueOnce(new Error("network"));

    const { result } = renderHook(() => useTickets());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.updateTicketStatus("ticket-1", "closed");
    });

    expect(result.current.tickets[0].status).toBe("open");
  });

  it("rolls back optimistic delete when the API call fails", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [makeTicket({ id: "ticket-1" }), makeTicket({ id: "ticket-2" })],
        total: 2,
        page: 1,
        size: 20,
      },
    });
    vi.mocked(api.delete).mockRejectedValueOnce(new Error("network"));

    const { result } = renderHook(() => useTickets());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await expect(
      act(async () => {
        await result.current.deleteTicket("ticket-1");
      }),
    ).rejects.toThrow();

    expect(result.current.tickets.map((ticket) => ticket.id)).toEqual(["ticket-1", "ticket-2"]);
    expect(result.current.total).toBe(2);
  });

  it("sets error state when the initial fetch fails", async () => {
    vi.mocked(api.get).mockRejectedValueOnce({
      response: { data: { detail: "Unauthorized" } },
    });

    const { result } = renderHook(() => useTickets());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBe("Unauthorized");
    expect(result.current.tickets).toHaveLength(0);
  });

  it("updateTicket patches the API and reflects the new data in the local list", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [makeTicket({ id: "ticket-1", title: "Original" })],
        total: 1,
        page: 1,
        size: 20,
      },
    });
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: makeTicket({ id: "ticket-1", title: "Updated title" }),
    });

    const { result } = renderHook(() => useTickets());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    let updated: Awaited<ReturnType<typeof result.current.updateTicket>>;
    await act(async () => {
      updated = await result.current.updateTicket("ticket-1", { title: "Updated title" });
    });

    expect(updated!.title).toBe("Updated title");
    expect(result.current.tickets[0].title).toBe("Updated title");
    expect(api.patch).toHaveBeenCalledWith("/tickets/ticket-1", { title: "Updated title" });
  });
});
