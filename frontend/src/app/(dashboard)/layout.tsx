/**
 * Dashboard layout — wraps all authenticated pages.
 *
 * This layout is shared by /board and /tickets/[id].
 * It renders the navigation header and the WebSocket connection hook.
 *
 * The Header component displays the user's avatar, the notification bell,
 * and the AI chat toggle button.
 *
 * Full implementation of Header and WebSocket hook: Día 4-5.
 */

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header with nav, notifications, AI chat toggle — Día 4 */}
      <header className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <span className="font-bold text-slate-800">D4-Ticket AI</span>
          <span className="text-sm text-slate-400">Header — coming Día 4</span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto">{children}</main>
    </div>
  );
}
