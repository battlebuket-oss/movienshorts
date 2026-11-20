import { NextResponse } from "next/server";

import { fetchBackend } from "@/server/backend-api";
import { getServerSession } from "@/server/session";

function safeReturnTo(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return "/";
  return value;
}

export async function GET(request: Request) {
  const session = await getServerSession();
  const returnTo = safeReturnTo(new URL(request.url).searchParams.get("returnTo"));
  const origin = new URL(request.url).origin;

  if (!session?.user?.id) return NextResponse.redirect(new URL("/sign-in", origin));

  let upstream: Response;
  try {
    upstream = await fetchBackend("/youtube/connect", {
      method: "GET",
      userId: session.user.id,
      cache: "no-store",
    });
  } catch {
    const target = new URL(returnTo, origin);
    target.searchParams.set("youtube_error", "service_unavailable");
    return NextResponse.redirect(target);
  }

  if (!upstream.ok) {
    const target = new URL(returnTo, origin);
    target.searchParams.set("youtube_error", upstream.status === 503 ? "not_configured" : "connect_failed");
    return NextResponse.redirect(target);
  }

  const payload = (await upstream.json()) as { authorization_url?: string };
  if (!payload.authorization_url || !payload.authorization_url.startsWith("https://accounts.google.com/")) {
    const target = new URL(returnTo, origin);
    target.searchParams.set("youtube_error", "connect_failed");
    return NextResponse.redirect(target);
  }

  const response = NextResponse.redirect(payload.authorization_url);
  response.cookies.set("youtube_oauth_return_to", returnTo, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/api/youtube/callback",
    maxAge: 10 * 60,
  });
  return response;
}
