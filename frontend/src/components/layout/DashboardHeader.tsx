/**
 * DashboardHeader — top navigation bar for all authenticated pages.
 *
 * Contains:
 *  - App logo / name (links to /board)
 *  - Notification bell (real-time badge from Zustand store)
 *  - User avatar with dropdown (links to profile / logout)
 *
 * This is a Client Component because it reads from Zustand (authStore) and
 * uses the WebSocket hook to establish the real-time connection.
 *
 * The WebSocket token is passed from the Server Component layout via a cookie
 * (the HttpOnly JWT cannot be read by JS — the token is forwarded by the
 * Next.js server to this component as a plain string prop).
 */

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LogOut, User, Bot } from "lucide-react";
import useAuthStore from "@/stores/authStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import { useNotifications } from "@/hooks/useNotifications";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { ChatSidebar } from "@/components/ai-chat/ChatSidebar";
import api from "@/lib/api";

interface DashboardHeaderProps {
  /** JWT token forwarded from the server cookie (for the WebSocket auth URL) */
  token: string | null;
}

export function DashboardHeader({ token }: DashboardHeaderProps) {
  const router = useRouter();
  const { user } = useAuthStore();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  // Initialise real-time connection — safe to call unconditionally (hook handles null token)
  useWebSocket(token);

  // Load the initial notification list on mount
  useNotifications();

  const handleLogout = async () => {
    try {
      await api.post("/auth/logout");
    } catch (err) {
      // Ignore errors if backend is unreachable
    }
    // Manually clear the cookie just in case (essential for the Demo flow)
    document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT;";
    
    // Redirect and force a full refresh to clear any state
    router.push("/login");
    window.location.reload();
  };

  return (
    <>
    <header className="bg-white border-b border-slate-200 px-6 py-3 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Logo */}
        <Link href="/board" className="font-bold text-slate-800 text-lg tracking-tight hover:text-blue-600 transition-colors">
          D4-Ticket{" "}
          <span className="text-blue-600">AI</span>
        </Link>

        {/* Right side: notifications + user */}
        <div className="flex items-center gap-2">
          {/* AI Chat toggle */}
          <button
            onClick={() => setChatOpen((o) => !o)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              chatOpen
                ? "bg-blue-600 text-white"
                : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
            }`}
            aria-label="Toggle AI assistant"
          >
            <Bot className="w-4 h-4" />
            <span className="hidden sm:block">AI</span>
          </button>

          <NotificationBell />

          {/* User avatar + dropdown */}
          <div className="relative">
            <button
              onClick={() => setDropdownOpen((o) => !o)}
              className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
              aria-label="User menu"
            >
              <UserAvatar 
                src={user?.avatar_url} 
                name={user?.name || "User"} 
                size="sm" 
              />
              <span className="text-sm text-slate-700 hidden sm:block max-w-[140px] truncate">
                {user?.name}
              </span>
            </button>

            {dropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  aria-hidden
                  onClick={() => setDropdownOpen(false)}
                />
                <div className="absolute right-0 top-full mt-2 w-48 bg-white rounded-xl shadow-lg border border-slate-200 z-50 overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-100">
                    <p className="text-sm font-medium text-slate-800 truncate">{user?.name}</p>
                    <p className="text-xs text-slate-400 truncate">{user?.email}</p>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                    Sign out
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>

    {/* Floating AI chat panel — rendered outside the header so it overlays page content */}
    {chatOpen && <ChatSidebar onClose={() => setChatOpen(false)} />}
  </>
  );
}
