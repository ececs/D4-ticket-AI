/**
 * Next.js middleware — route protection.
 *
 * Next.js middleware runs on the Edge Runtime before every request.
 * It's ideal for auth guards because it executes before the page renders,
 * preventing a flash of unauthenticated content.
 *
 * Strategy:
 *  - Public routes (login, OAuth callback): accessible without a token.
 *  - All other routes: require the access_token cookie.
 *  - If the cookie is missing → redirect to /login.
 *  - If on /login with a valid token → redirect to /board (already logged in).
 *
 * Note: We only check for the cookie's existence here (fast, no DB query).
 * The actual token validity is verified by FastAPI on every API call.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that don't require authentication
const PUBLIC_PATHS = ["/login", "/api/auth"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("access_token")?.value;

  const isPublicPath = PUBLIC_PATHS.some((path) => pathname.startsWith(path));

  if (!isPublicPath && !token) {
    // No token → redirect to login, preserving the intended destination
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname); // e.g., ?next=/board
    return NextResponse.redirect(loginUrl);
  }

  if (pathname === "/login" && token) {
    // Already authenticated → redirect away from login
    return NextResponse.redirect(new URL("/board", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Apply middleware to all routes except Next.js internals and static files
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
