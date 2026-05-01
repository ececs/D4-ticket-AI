/**
 * Board page — main dashboard.
 *
 * This is a Server Component shell. The actual board content (list/kanban toggle,
 * filtering, drag & drop) is implemented in client components imported below.
 *
 * Server Components can fetch data directly (no client-side JS needed for initial load).
 * However, since this app is behind authentication and has real-time requirements,
 * the data fetching is done in the client components to benefit from the WebSocket connection.
 *
 * Full implementation: Día 3-4.
 */

export default function BoardPage() {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Tickets</h1>
        <p className="text-slate-500 text-sm mt-1">
          Manage and track all work items
        </p>
      </div>
      {/* BoardContent client component will be added in Día 3 */}
      <p className="text-slate-400">Board content coming in Día 3...</p>
    </div>
  );
}
