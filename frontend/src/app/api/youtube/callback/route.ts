import { NextResponse } from "next/server";

import { fetchBackend } from "@/server/backend-api";
import { getServerSession } from "@/server/session";

function safeReturnTo(value: string | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return "/";
  return value;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const origin = url.origin;
  const cookieHeader = request.headers.get("cookie") ?? "";
  const returnCookie = cookieHeader.split(";").map((part) => part.trim()).find((part) => part.startsWith("youtube_oauth_return_to="));
  let decodedReturnTo: string | undefined;
  try {
    decodedReturnTo = returnCookie ? decodeURIComponent(returnCookie.slice("youtube_oauth_return_to=".length)) : undefined;
  } catch {
    decodedReturnTo = undefined;
  }
  const returnTo = safeReturnTo(decodedReturnTo);

  const redirectWith = (key: string, value: string) => {
    const target = new URL(returnTo, origin);
    target.searchParams.set(key, value);
    const response = NextResponse.redirect(target);
    response.cookies.set("youtube_oauth_return_to", "", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/api/youtube/callback",
      maxAge: 0,
    });
    return response;
  };

  if (url.searchParams.get("error")) return redirectWith("youtube_error", "authorization_denied");

  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  if (!code || !state) return redirectWith("youtube_error", "invalid_callback");

  const session = await getServerSession();
  if (!session?.user?.id) return redirectWith("youtube_error", "session_expired");

  try {
    const upstream = await fetchBackend("/youtube/callback", {
      method: "POST",
      userId: session.user.id,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, state }),
      cache: "no-store",
    });
    if (!upstream.ok) {
      return redirectWith("youtube_error", upstream.status === 503 ? "not_configured" : "connection_failed");
    }
    return redirectWith("youtube", "connected");
  } catch {
    return redirectWith("youtube_error", "connection_failed");
  }
}
