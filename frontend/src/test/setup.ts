import { afterEach, vi } from "vitest";
import useNotificationStore from "@/stores/notificationStore";

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
  useNotificationStore.setState({
    notifications: [],
    unreadCount: 0,
    refreshSignal: 0,
    lastTicketId: null,
    deletedTicketId: null,
  });
});
