/**
 * useWebSocket — real-time notification hook.
 *
 * Connects to the FastAPI WebSocket endpoint (/ws?token=<jwt>) and
 * pushes incoming notifications into the Zustand notification store.
 *
 * Connection lifecycle:
 *  1. On mount: extract the JWT from the access_token cookie and connect.
 *  2. Reconnect: if the connection closes unexpectedly (network hiccup),
 *     wait 3 seconds and retry automatically.
 *  3. On unmount: close the connection cleanly to avoid memory leaks.
 *
 * Why cookies and not a zustand token?
 *   The JWT is stored in an HttpOnly cookie — JavaScript cannot read it via
 *   document.cookie. We pass it as a URL query parameter (?token=...) because
 *   native WebSocket connections don't support custom headers.
 *   The cookie value is readable from Next.js server context, so we pass it
 *   down as a prop from the server layout.
 */

"use client";

import { useEffect, useRef } from "react";
import useNotificationStore from "@/stores/notificationStore";
import { Notification } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_API_URL?.replace("http", "ws") ?? "ws://localhost:8000";

export function useWebSocket(token: string | null) {
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
  const { addNotification, triggerRefresh } = useNotificationStore();

  useEffect(() => {
    if (!token) return; // Not authenticated yet

    const connect = () => {
      // Close any existing connection before creating a new one
      if (ws.current) {
        ws.current.onclose = null; // Prevent reconnect loop on manual close
        ws.current.close();
      }

      // Clean the URL to avoid double slashes if NEXT_PUBLIC_API_URL ends with /
      const baseUrl = WS_URL.endsWith("/") ? WS_URL.slice(0, -1) : WS_URL;
      const socket = new WebSocket(`${baseUrl}/ws?token=${token}`);
      ws.current = socket;

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as Record<string, unknown>;
          // Ignore keepalive pings
          if (data.type === "ping") return;

          // Special case: web_scrape_completed is a virtual event (not in DB)
          if (data.type === "web_scrape_completed" && data.ticket_id) {
            triggerRefresh(String(data.ticket_id));
            return;
          }

          // Persistent notifications must have an id and ticket_id
          if (!data.id || !data.ticket_id) return;
          
          addNotification(data as unknown as Notification);
          
          // Trigger a refresh of any components listening to the refresh signal
          triggerRefresh(String(data.ticket_id));
        } catch {
          // Ignore malformed messages
        }
      };

      socket.onclose = (event) => {
        console.log(`WebSocket closed: ${event.code} ${event.reason}`);
        // Attempt to reconnect after 2 seconds unless it was a clean close
        if (event.code !== 1000) {
          reconnectTimeout.current = setTimeout(connect, 2000);
        }
      };

      socket.onerror = () => {
        socket.close(); // onclose will handle reconnect
      };
    };

    connect();

    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) {
        ws.current.onclose = null; // Prevent reconnect on cleanup
        ws.current.close(1000, "Component unmounted");
      }
    };
  }, [token, addNotification]);
}
