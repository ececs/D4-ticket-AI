import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { makeNotification } from "@/test/factories";
import { useWebSocket } from "@/hooks/useWebSocket";

const storeActions = {
  addNotification: vi.fn(),
  syncRemoveNotification: vi.fn(),
  syncMarkOneRead: vi.fn(),
  triggerRefresh: vi.fn(),
  triggerDelete: vi.fn(),
  syncUnreadCount: vi.fn(),
  syncMarkAllAsRead: vi.fn(),
};

const toastMock = vi.fn();

vi.mock("@/stores/notificationStore", () => ({
  default: vi.fn(() => storeActions),
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: toastMock }),
}));

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
}

describe("useWebSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    Object.assign(globalThis, { WebSocket: FakeWebSocket });
    Object.values(storeActions).forEach((fn) => fn.mockReset());
    toastMock.mockReset();
  });

  it("does not connect without a token", () => {
    renderHook(() => useWebSocket(null));

    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it("connects with the token and handles ticket events", () => {
    renderHook(() => useWebSocket("jwt-123"));
    const socket = FakeWebSocket.instances[0];

    expect(socket.url).toContain("/ws?token=jwt-123");

    act(() => {
      socket.onmessage?.({
        data: JSON.stringify({ type: "ticket_created", data: { id: "ticket-1" } }),
      } as MessageEvent<string>);
      socket.onmessage?.({
        data: JSON.stringify({ type: "ticket_deleted", data: { id: "ticket-2" } }),
      } as MessageEvent<string>);
      socket.onmessage?.({
        data: JSON.stringify({ type: "ticket_updated", ticket_id: "ticket-3" }),
      } as MessageEvent<string>);
    });

    expect(storeActions.triggerRefresh).toHaveBeenCalledWith("ticket-1");
    expect(storeActions.triggerDelete).toHaveBeenCalledWith("ticket-2");
    expect(storeActions.triggerRefresh).toHaveBeenCalledWith("ticket-3");
  });

  it("pushes notifications and keeps badge state in sync", () => {
    renderHook(() => useWebSocket("jwt-123"));
    const socket = FakeWebSocket.instances[0];
    const notification = makeNotification({ id: "n-1", message: "Assigned to you" });

    act(() => {
      socket.onmessage?.({
        data: JSON.stringify({
          type: "notification",
          data: { ...notification, unread_count: 4, ticket_id: "ticket-9" },
        }),
      } as MessageEvent<string>);
      socket.onmessage?.({
        data: JSON.stringify({ type: "notification_read", data: { id: "n-1", unread_count: 3 } }),
      } as MessageEvent<string>);
      socket.onmessage?.({
        data: JSON.stringify({ type: "notifications_read_all", data: { unread_count: 0 } }),
      } as MessageEvent<string>);
      socket.onmessage?.({
        data: JSON.stringify({ type: "notification_deleted", data: { id: "n-1", unread_count: 0 } }),
      } as MessageEvent<string>);
    });

    expect(storeActions.addNotification).toHaveBeenCalledWith(expect.objectContaining({ id: "n-1" }), 4);
    expect(storeActions.triggerRefresh).toHaveBeenCalledWith("ticket-9");
    expect(storeActions.syncMarkOneRead).toHaveBeenCalledWith("n-1", 3);
    expect(storeActions.syncMarkAllAsRead).toHaveBeenCalledWith(0);
    expect(storeActions.syncRemoveNotification).toHaveBeenCalledWith("n-1", 0);
    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({ title: "Nueva Notificación" }));
  });

  it("syncs initial unread count without showing a toast for the handshake", () => {
    renderHook(() => useWebSocket("jwt-123"));
    const socket = FakeWebSocket.instances[0];

    act(() => {
      socket.onmessage?.({
        data: JSON.stringify({
          type: "system_alert",
          data: { unread_count: 5 },
          message: "Estado inicial cargado",
        }),
      } as MessageEvent<string>);
    });

    expect(storeActions.syncUnreadCount).toHaveBeenCalledWith(5);
    expect(toastMock).not.toHaveBeenCalled();
  });

  it("shows a toast for scrape completion and reconnects after abnormal close", () => {
    renderHook(() => useWebSocket("jwt-123"));
    const socket = FakeWebSocket.instances[0];

    act(() => {
      socket.onmessage?.({
        data: JSON.stringify({
          type: "web_scrape_completed",
          ticket_id: "ticket-4",
          message: "Resumen generado",
        }),
      } as MessageEvent<string>);
    });

    expect(storeActions.triggerRefresh).toHaveBeenCalledWith("ticket-4");
    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({ title: "Análisis Web Finalizado" }));

    act(() => {
      socket.onclose?.({ code: 1006, reason: "network" } as CloseEvent);
      vi.advanceTimersByTime(2000);
    });

    expect(FakeWebSocket.instances).toHaveLength(2);
  });
});
