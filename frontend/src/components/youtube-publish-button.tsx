"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Youtube, Loader2, ExternalLink, AlertCircle } from "lucide-react";

type Props = {
  clipId: string;
  defaultTitle: string;
  returnTo: string;
};

export default function YoutubePublishButton({ clipId, defaultTitle, returnTo }: Props) {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [title, setTitle] = useState(defaultTitle.slice(0, 100));
  const [description, setDescription] = useState("");
  const [privacy, setPrivacy] = useState<"private" | "unlisted" | "public">("private");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadedUrl, setUploadedUrl] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch("/api/youtube/status", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not check your YouTube connection.");
        const result = await response.json();
        if (active) setConnected(Boolean(result.connected));
      })
      .catch(() => { if (active) setConnected(false); });
    return () => { active = false; };
  }, []);

  const upload = async () => {
    if (!title.trim()) {
      setError("Enter a title for the Short.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const response = await fetch("/api/youtube/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clip_id: clipId,
          title: title.trim(),
          description,
          privacy_status: privacy,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || result.error || "YouTube upload failed.");
      setUploadedUrl(result.video_url);
      setExpanded(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "YouTube upload failed.");
    } finally {
      setUploading(false);
    }
  };

  if (uploadedUrl) {
    return (
      <a href={uploadedUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm font-medium text-green-700 hover:underline">
        <ExternalLink className="h-4 w-4" /> View on YouTube
      </a>
    );
  }

  if (connected === false) {
    return (
      <Button size="sm" variant="outline" asChild>
        <a href={"/api/youtube/connect?returnTo=" + encodeURIComponent(returnTo)}>
          <Youtube className="mr-2 h-4 w-4" /> Connect YouTube
        </a>
      </Button>
    );
  }

  if (connected === null) return <Button size="sm" variant="outline" disabled>Checking YouTube…</Button>;

  return (
    <div className="space-y-2">
      {!expanded ? (
        <Button size="sm" variant="outline" onClick={() => setExpanded(true)}>
          <Youtube className="mr-2 h-4 w-4" /> Upload to YouTube
        </Button>
      ) : (
        <div className="w-full max-w-md rounded-lg border border-stone-200 bg-stone-50 p-3 space-y-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-stone-600" htmlFor={"youtube-title-" + clipId}>Short title</label>
            <Input id={"youtube-title-" + clipId} maxLength={100} value={title} onChange={(event) => setTitle(event.target.value)} />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-stone-600" htmlFor={"youtube-description-" + clipId}>Description (optional)</label>
            <textarea id={"youtube-description-" + clipId} maxLength={5000} value={description} onChange={(event) => setDescription(event.target.value)} rows={3} className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm" />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-stone-600" htmlFor={"youtube-privacy-" + clipId}>Visibility</label>
            <select id={"youtube-privacy-" + clipId} value={privacy} onChange={(event) => setPrivacy(event.target.value as typeof privacy)} className="h-9 w-full rounded-md border border-stone-300 bg-white px-3 text-sm">
              <option value="private">Private (recommended)</option>
              <option value="unlisted">Unlisted</option>
              <option value="public">Public</option>
            </select>
          </div>
          <p className="text-xs text-stone-500">The video uploads only when you confirm below. Private is selected by default.</p>
          {error && <p className="flex items-start gap-1.5 text-xs text-red-600"><AlertCircle className="h-4 w-4 shrink-0" />{error}</p>}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={upload} disabled={uploading || !title.trim()}>
              {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Youtube className="mr-2 h-4 w-4" />}
              {uploading ? "Uploading…" : "Confirm upload"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => { setExpanded(false); setError(null); }} disabled={uploading}>Cancel</Button>
          </div>
        </div>
      )}
      {error && !expanded && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
