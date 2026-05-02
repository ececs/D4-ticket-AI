import { NextRequest, NextResponse } from "next/server";

/**
 * Server-side cookie clearing endpoint.
 *
 * JavaScript cannot delete httpOnly cookies — only the server can.
 * The axios 401 interceptor redirects here to clear any stale session
 * (whether httpOnly or not) before sending the user to /login.
 */
export async function GET(request: NextRequest) {
  const response = NextResponse.redirect(new URL("/login", request.url));
  // Server-side delete works for both httpOnly and non-httpOnly cookies
  response.cookies.delete("access_token");
  return response;
}
