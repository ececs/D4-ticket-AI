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
import { useToast } from "@/hooks/use-toast";

const WS_URL = process.env.NEXT_PUBLIC_API_URL?.replace("http", "ws") ?? "ws://localhost:8000";

export function useWebSocket(token: string | null) {
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
  const { addNotification, triggerRefresh, syncUnreadCount } = useNotificationStore();
  const { toast } = useToast();

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
          const wsMsg = JSON.parse(event.data);
          const { type, data, ticket_id, message } = wsMsg;

          // Ignore keepalive pings
          if (type === "ping") return;

          switch (type) {
            case "web_scrape_completed":
              if (ticket_id) {
                triggerRefresh(String(ticket_id));
                toast({
                  title: "Análisis Web Finalizado",
                  description: message || "La IA ha terminado de analizar la URL del cliente.",
                  variant: "success",
                });
              }
              break;

            case "notification":
              if (data && data.id) {
                // Pass the server's authoritative unread_count so the badge is
                // always accurate even when the notification is a duplicate.
                addNotification(
                  data as unknown as Notification,
                  typeof data.unread_count === "number" ? data.unread_count : undefined,
                );
                if (data.ticket_id) triggerRefresh(String(data.ticket_id));

                toast({
                  title: "Nueva Notificación",
                  description: data.message || "Tienes una nueva actualización.",
                });
              }
              break;

            case "ticket_updated":
              if (ticket_id) {
                triggerRefresh(String(ticket_id));
              }
              break;
              
            case "system_alert":
              // Sync badge with the authoritative count from the initial WS handshake
              if (data && typeof data.unread_count === "number") {
                syncUnreadCount(data.unread_count);
              }
              // Only show a toast for real alerts, not for the connection handshake
              if (message && message !== "Estado inicial cargado") {
                toast({
                  title: "Aviso del Sistema",
                  description: message,
                  variant: message.toLowerCase().includes("error") ? "destructive" : "default",
                });
              }
              break;

            default:
              console.warn("Unknown WebSocket message type:", type);
          }
        } catch (err) {
          console.error("Failed to parse WebSocket message:", err);
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
