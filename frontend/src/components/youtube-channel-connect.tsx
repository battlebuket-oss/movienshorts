"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Youtube, Unlink, Loader2, CheckCircle2, AlertCircle } from "lucide-react";

type ChannelStatus = {
  connected: boolean;
  channel: { id: string; title: string; connected_at: string | null } | null;
};

export default function YoutubeChannelConnect({ returnTo = "/" }: { returnTo?: string }) {
  const [status, setStatus] = useState<ChannelStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/youtube/status", { cache: "no-store" });
      if (!response.ok) throw new Error("Could not check the YouTube connection.");
      setStatus((await response.json()) as ChannelStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not check the YouTube connection.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const disconnect = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/youtube/disconnect", { method: "DELETE" });
      if (!response.ok) throw new Error("Could not disconnect the YouTube channel.");
      setStatus({ connected: false, channel: null });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disconnect the YouTube channel.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <div className="rounded-lg bg-red-50 p-2 text-red-600"><Youtube className="h-5 w-5" /></div>
        <div className="min-w-0">
          <p className="font-semibold text-stone-900">YouTube channel</p>
          {loading ? (
            <p className="text-sm text-stone-500">Checking connection…</p>
          ) : status?.connected && status.channel ? (
            <p className="flex items-center gap-1.5 text-sm text-stone-600">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              Connected to <span className="font-medium text-stone-900">{status.channel.title}</span>
            </p>
          ) : (
            <p className="text-sm text-stone-500">Connect your channel to upload finished clips directly.</p>
          )}
        </div>
      </div>
      {status?.connected ? (
        <Button variant="outline" size="sm" onClick={disconnect} disabled={busy}>
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Unlink className="mr-2 h-4 w-4" />}
          Disconnect
        </Button>
      ) : (
        <Button asChild size="sm" disabled={loading || busy}>
          <a href={"/api/youtube/connect?returnTo=" + encodeURIComponent(returnTo)}>
            <Youtube className="mr-2 h-4 w-4" />
            Connect YouTube
          </a>
        </Button>
      )}
      {error && (
        <Alert variant="destructive" className="sm:basis-full">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </section>
  );
}
