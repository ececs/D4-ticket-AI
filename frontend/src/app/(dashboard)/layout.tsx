/**
 * Dashboard layout — wraps all authenticated pages.
 *
 * This is a Server Component. It reads the `access_token` cookie and passes
 * it as a plain string to DashboardHeader (a Client Component) so the WebSocket
 * hook can authenticate with the FastAPI WS endpoint via a query parameter.
 *
 * Why not read the cookie in the client component?
 *   The JWT is stored in an HttpOnly cookie — browser JS cannot access it.
 *   Next.js server components CAN read it via `cookies()`. We forward it as a
 *   string prop; it is used only to construct the WebSocket URL and is never
 *   rendered in the HTML, so the exposure risk is minimal and equivalent to
 *   the existing WS connection that already transmits the token in the URL.
 *
 * AuthInitializer:
 *   Calls GET /auth/me on mount and populates the Zustand authStore so all
 *   client components can access the current user without prop drilling.
 */

import { cookies } from "next/headers";
import { DashboardHeader } from "@/components/layout/DashboardHeader";
import { AuthInitializer } from "@/components/layout/AuthInitializer";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value ?? null;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Hydrate the Zustand auth store on first render */}
      <AuthInitializer />

      {/* Sticky header: logo + notification bell + user menu */}
      <DashboardHeader token={token} />

      <main className="max-w-7xl mx-auto">{children}</main>
    </div>
  );
}
