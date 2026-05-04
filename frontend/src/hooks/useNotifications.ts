/**
 * useNotifications — fetches the initial notification list from the API and
 * syncs it to the Zustand notification store.
 *
 * The store's markAsRead / markAllAsRead actions already call the API and update
 * local state, so this hook just exposes them as named callbacks for convenience.
 *
 * The real-time feed is handled separately by useWebSocket, which pushes new
 * notifications into the store as they arrive over the WS connection.
 */

"use client";

import { useEffect } from "react";
import api from "@/lib/api";
import useNotificationStore from "@/stores/notificationStore";
import { Notification } from "@/types";

export function useNotifications() {
  const { setNotifications, markAsRead, markAllAsRead, removeNotification } = useNotificationStore();

  // Load initial list on mount
  useEffect(() => {
    api.get<Notification[]>("/notifications").then(({ data }) => {
      setNotifications(data);
    });
  }, [setNotifications]);

  // The store actions already call the API — expose them directly
  return {
    handleMarkAsRead: markAsRead,
    handleMarkAllAsRead: markAllAsRead,
    handleDeleteNotification: removeNotification,
  };
}
