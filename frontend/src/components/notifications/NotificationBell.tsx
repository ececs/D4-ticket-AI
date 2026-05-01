/**
 * NotificationBell — icon button with an unread count badge.
 *
 * Reads the unread count from the Zustand notification store, which is updated
 * in real-time by useWebSocket. Clicking the bell toggles the NotificationPanel.
 *
 * The panel closes when the user clicks outside it (via the invisible overlay div).
 */

"use client";

import { useState } from "react";
import { Bell } from "lucide-react";
import useNotificationStore from "@/stores/notificationStore";
import { NotificationPanel } from "./NotificationPanel";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const unreadCount = useNotificationStore((s) => s.unreadCount);

  return (
    <div className="relative">
      {/* Bell button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative p-2 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold px-1 leading-none">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {/* Panel + click-outside overlay */}
      {open && (
        <>
          <div
            className="fixed inset-0 z-40"
            aria-hidden
            onClick={() => setOpen(false)}
          />
          <NotificationPanel onClose={() => setOpen(false)} />
        </>
      )}
    </div>
  );
}
