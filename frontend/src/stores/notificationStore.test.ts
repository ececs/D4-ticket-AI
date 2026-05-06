import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import useNotificationStore from "@/stores/notificationStore";
import { makeNotification } from "@/test/factories";

vi.mock("@/lib/api", () => ({
  default: {
    delete: vi.fn(),
    patch: vi.fn(),
  },
}));

describe("notificationStore", () => {
  beforeEach(() => {
    useNotificationStore.setState({
      notifications: [],
      unreadCount: 0,
      refreshSignal: 0,
      lastTicketId: null,
      deletedTicketId: null,
    });
  });

  it("deduplicates notifications on setNotifications and derives unread count", () => {
    const first = makeNotification({ id: "n-1", read: false });
    const duplicate = makeNotification({ id: "n-1", message: "Duplicate payload" });
    const second = makeNotification({ id: "n-2", read: true });

    useNotificationStore.getState().setNotifications([first, duplicate, second]);
    const state = useNotificationStore.getState();

    expect(state.notifications).toHaveLength(2);
    expect(state.unreadCount).toBe(1);
  });

  it("adds a new notification and trusts server unread count", () => {
    useNotificationStore.getState().addNotification(makeNotification({ id: "n-1" }), 7);

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(1);
    expect(state.unreadCount).toBe(7);
  });

  it("does not duplicate notifications and still syncs unread count", () => {
    const notification = makeNotification({ id: "n-1" });
    const store = useNotificationStore.getState();
    store.addNotification(notification, 1);
    store.addNotification(notification, 3);

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(1);
    expect(state.unreadCount).toBe(3);
  });

  it("marks one notification as read using fallback count derivation", () => {
    useNotificationStore.setState({
      notifications: [
        makeNotification({ id: "n-1", read: false }),
        makeNotification({ id: "n-2", read: false }),
      ],
      unreadCount: 2,
    });

    useNotificationStore.getState().syncMarkOneRead("n-1");
    const state = useNotificationStore.getState();

    expect(state.notifications.find((n) => n.id === "n-1")?.read).toBe(true);
    expect(state.unreadCount).toBe(1);
  });

  it("marks all notifications as read and zeroes the badge", () => {
    useNotificationStore.setState({
      notifications: [
        makeNotification({ id: "n-1", read: false }),
        makeNotification({ id: "n-2", read: false }),
      ],
      unreadCount: 2,
    });

    useNotificationStore.getState().syncMarkAllAsRead();
    const state = useNotificationStore.getState();

    expect(state.notifications.every((n) => n.read)).toBe(true);
    expect(state.unreadCount).toBe(0);
  });

  it("updates refresh/delete markers consistently", () => {
    const store = useNotificationStore.getState();

    store.triggerRefresh("ticket-1");
    let state = useNotificationStore.getState();
    expect(state.refreshSignal).toBe(1);
    expect(state.lastTicketId).toBe("ticket-1");
    expect(state.deletedTicketId).toBeNull();

    store.triggerDelete("ticket-9");
    state = useNotificationStore.getState();
    expect(state.refreshSignal).toBe(2);
    expect(state.lastTicketId).toBeNull();
    expect(state.deletedTicketId).toBe("ticket-9");

    store.triggerDelete("");
    state = useNotificationStore.getState();
    expect(state.refreshSignal).toBe(2);
    expect(state.deletedTicketId).toBeNull();
  });

  it("keeps optimistic removal when backend deletion fails", async () => {
    vi.mocked(api.delete).mockRejectedValueOnce(new Error("network"));
    useNotificationStore.setState({
      notifications: [makeNotification({ id: "n-1" }), makeNotification({ id: "n-2", read: true })],
      unreadCount: 1,
    });

    await useNotificationStore.getState().removeNotification("n-1");
    const state = useNotificationStore.getState();

    expect(state.notifications.map((n) => n.id)).toEqual(["n-2"]);
    expect(state.unreadCount).toBe(0);
  });

  it("marks one notification as read optimistically even if the API call fails", async () => {
    vi.mocked(api.patch).mockRejectedValueOnce(new Error("network"));
    useNotificationStore.setState({
      notifications: [makeNotification({ id: "n-1", read: false })],
      unreadCount: 1,
    });

    await useNotificationStore.getState().markAsRead("n-1");
    const state = useNotificationStore.getState();

    expect(state.notifications[0].read).toBe(true);
    expect(state.unreadCount).toBe(0);
  });

  it("markAllAsRead marks all notifications as read and zeroes the badge", async () => {
    useNotificationStore.setState({
      notifications: [
        makeNotification({ id: "n-1", read: false }),
        makeNotification({ id: "n-2", read: false }),
      ],
      unreadCount: 2,
    });

    await useNotificationStore.getState().markAllAsRead();
    const state = useNotificationStore.getState();

    expect(state.notifications.every((n) => n.read)).toBe(true);
    expect(state.unreadCount).toBe(0);
  });

  it("syncRemoveNotification removes a notification and derives unread count", () => {
    useNotificationStore.setState({
      notifications: [
        makeNotification({ id: "n-1", read: false }),
        makeNotification({ id: "n-2", read: true }),
      ],
      unreadCount: 1,
    });

    useNotificationStore.getState().syncRemoveNotification("n-1");
    const state = useNotificationStore.getState();

    expect(state.notifications.map((n) => n.id)).toEqual(["n-2"]);
    expect(state.unreadCount).toBe(0);
  });

  it("syncRemoveNotification trusts server unread count when provided", () => {
    useNotificationStore.setState({
      notifications: [
        makeNotification({ id: "n-1", read: false }),
        makeNotification({ id: "n-2", read: false }),
      ],
      unreadCount: 2,
    });

    useNotificationStore.getState().syncRemoveNotification("n-1", 5);
    const state = useNotificationStore.getState();

    expect(state.unreadCount).toBe(5);
  });

  it("syncMarkOneRead uses server count over local derivation when provided", () => {
    useNotificationStore.setState({
      notifications: [
        makeNotification({ id: "n-1", read: false }),
        makeNotification({ id: "n-2", read: false }),
      ],
      unreadCount: 2,
    });

    useNotificationStore.getState().syncMarkOneRead("n-1", 7);
    const state = useNotificationStore.getState();

    expect(state.notifications.find((n) => n.id === "n-1")?.read).toBe(true);
    expect(state.unreadCount).toBe(7);
  });

  it("syncMarkAllAsRead uses server count when provided instead of hardcoding zero", () => {
    useNotificationStore.setState({
      notifications: [makeNotification({ id: "n-1", read: false })],
      unreadCount: 1,
    });

    useNotificationStore.getState().syncMarkAllAsRead(0);
    const state = useNotificationStore.getState();

    expect(state.notifications.every((n) => n.read)).toBe(true);
    expect(state.unreadCount).toBe(0);
  });
});
