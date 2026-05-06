/**
 * Next.js proxy — route protection.
 *
 * In Next.js 16, the old middleware convention was renamed to proxy.
 * We keep the same auth-guard behavior while following the current API.
 *
 * Strategy:
 *  - Public routes (login, OAuth callback): accessible without a token.
 *  - All other routes: require the access_token cookie.
 *  - If the cookie is missing -> redirect to /login.
 *  - If on /login with a valid token -> redirect to /board.
 *
 * Note: We only check for the cookie's existence here (fast, no DB query).
 * The actual token validity is verified by FastAPI on every API call.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login", "/api/auth", "/_next"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("access_token")?.value;

  const isPublicPath = PUBLIC_PATHS.some((path) => pathname.startsWith(path));

  if (!isPublicPath && !token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (pathname === "/login" && token) {
    return NextResponse.redirect(new URL("/board", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
