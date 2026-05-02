import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get("token");

  if (!token) {
    return NextResponse.redirect(new URL("/login?error=missing_token", request.url));
  }

  const response = NextResponse.redirect(new URL("/board", request.url));

  const maxAge = 60 * 60 * 24 * 7; // 7 days
  // Not httpOnly so the axios client can read it and send as Authorization: Bearer
  // to the Railway backend (different domain — cookies aren't shared cross-domain).
  // The Next.js middleware also reads this cookie server-side for route protection.
  response.cookies.set("access_token", token, {
    httpOnly: false,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge,
    path: "/",
  });

  return response;
}
