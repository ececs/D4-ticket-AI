/**
 * Notification state store — Zustand.
 *
 * Manages the list of notifications and the unread badge count.
 * Notifications arrive via two channels:
 *  1. Initial load: from GET /notifications on first WebSocket connect.
 *  2. Real-time: pushed via WebSocket as events happen.
 *
 * The `unreadCount` is derived from the notifications array (not stored separately)
 * to avoid state synchronization bugs.
 */

import { create } from "zustand";
import { Notification } from "@/types";
import api from "@/lib/api";

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  refreshSignal: number;
  lastTicketId: string | null;
  addNotification: (notification: Notification, serverUnreadCount?: number) => void;
  syncUnreadCount: (count: number) => void;
  triggerRefresh: (ticketId?: string) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  setNotifications: (notifications: Notification[]) => void;
}

const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  unreadCount: 0,
  refreshSignal: 0,
  lastTicketId: null,

  triggerRefresh: (ticketId) =>
    set((state) => ({
      refreshSignal: state.refreshSignal + 1,
      lastTicketId: ticketId || null
    })),

  // Sync badge count directly from the server-authoritative value
  syncUnreadCount: (count) => set({ unreadCount: count }),

  setNotifications: (notifications) => {
    // Use a Map to ensure absolute uniqueness by ID
    const uniqueMap = new Map();
    notifications.forEach((n) => uniqueMap.set(n.id, n));
    const unique = Array.from(uniqueMap.values());
    
    set({
      notifications: unique,
      unreadCount: unique.filter((n) => !n.read).length,
    });
  },

  addNotification: (notification, serverUnreadCount) => {
    set((state) => {
      if (state.notifications.some((n) => n.id === notification.id)) {
        // Even on a duplicate, trust the server's authoritative count if provided
        if (typeof serverUnreadCount === "number") {
          return { ...state, unreadCount: serverUnreadCount };
        }
        return state;
      }
      const updated = [notification, ...state.notifications];
      return {
        notifications: updated,
        unreadCount: typeof serverUnreadCount === "number"
          ? serverUnreadCount
          : updated.filter((n) => !n.read).length,
      };
    });
  },

  markAsRead: async (id) => {
    try {
      await api.patch(`/notifications/${id}/read`);
    } catch {
      // Optimistic update — don't revert on failure for UX simplicity
    }
    set((state) => {
      const updated = state.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      );
      return {
        notifications: updated,
        unreadCount: updated.filter((n) => !n.read).length,
      };
    });
  },

  markAllAsRead: async () => {
    try {
      await api.patch("/notifications/read-all");
    } catch {
      // Optimistic update
    }
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    }));
  },
}));

export default useNotificationStore;
