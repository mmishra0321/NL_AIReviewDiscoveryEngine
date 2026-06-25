import { useEffect, useState } from "react";
import { Download, RefreshCw, Clock, Database, ListFilter } from "lucide-react";
import { api } from "@/lib/api";
import type { Meta } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import { formatNumber, formatRelativeTime, sourceColor, sourceLabel } from "@/lib/utils";

export function MetadataBar({ onRefreshed }: { onRefreshed?: () => void }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloading, setReloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setMeta(await api.meta());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function handleReload() {
    setReloading(true);
    try {
      await fetch(`${import.meta.env.VITE_API_BASE ?? ""}/api/admin/reload`, { method: "POST" });
      await load();
      onRefreshed?.();
    } finally {
      setReloading(false);
    }
  }

  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-14 rounded-lg" />)}
      </div>
    );
  }
  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-300">
        Backend not reachable: {error}. Start it with{" "}
        <code className="font-mono bg-bg-subtle px-1.5 py-0.5 rounded">uvicorn backend.main:app --reload --port 8000</code>.
      </div>
    );
  }
  if (!meta) return null;

  const scrapeCounts = meta.scrape_counts_this_run ?? {};
  const scrapedThisRun = Object.values(scrapeCounts).reduce((a, b) => a + b, 0);
  const relevancePct = meta.total_relevant && meta.total_normalized
    ? Math.round((meta.total_relevant / meta.total_normalized) * 100)
    : 0;

  return (
    <div className="space-y-3 animate-fade-in">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
        <Stat icon={<Clock className="w-3.5 h-3.5" />} label="Last refresh"
              value={formatRelativeTime(meta.last_refresh_utc)}
              sub={meta.last_refresh_utc ? new Date(meta.last_refresh_utc).toUTCString() : undefined} />
        <Stat icon={<Database className="w-3.5 h-3.5" />} label="Normalized"
              value={formatNumber(meta.total_normalized)} sub="capped to 1000" />
        <Stat icon={<ListFilter className="w-3.5 h-3.5" />} label="Discovery-relevant"
              value={formatNumber(meta.total_relevant)} sub={`${relevancePct}% of capped`} />
        <Stat label="Indexed in Chroma" value={formatNumber(meta.chroma_collection_size)} sub="embeddings" />
        <Stat
          label="Scraped this run"
          value={scrapedThisRun > 0 ? formatNumber(scrapedThisRun) : "-"}
          sub={scrapedThisRun > 0
            ? Object.entries(scrapeCounts).map(([k, v]) => `${k}:${v}`).join(" · ")
            : "reused cached raw"}
        />
        <div className="flex items-center justify-end gap-2 col-span-2 md:col-span-1">
          <a href={api.exportUrl()} download>
            <Button variant="primary" size="sm" className="w-full">
              <Download className="w-3.5 h-3.5" /> Excel
            </Button>
          </a>
          <Button variant="secondary" size="sm" onClick={handleReload} disabled={reloading}>
            <RefreshCw className={`w-3.5 h-3.5 ${reloading ? "animate-spin" : ""}`} />
            Reload
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="text-fg-subtle pr-1">By source:</span>
        {Object.entries(meta.by_source ?? {}).map(([src, n]) => (
          <span key={src}
                className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 ${sourceColor(src)}`}>
            <strong>{formatNumber(n)}</strong>
            <span className="opacity-80">{sourceLabel(src)}</span>
          </span>
        ))}
        <span className="text-fg-subtle pl-2">·  Tagged:</span>
        {Object.entries(meta.by_canonical_tag ?? {}).map(([tag, n]) => (
          <Badge key={tag} tone="info">{tag.replace(/^Q\d+_/, "")} · {n}</Badge>
        ))}
      </div>
    </div>
  );
}

function Stat({ icon, label, value, sub }: { icon?: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-border bg-bg-elevated px-3 py-2.5">
      <div className="flex items-center gap-1 text-[11px] uppercase tracking-wider text-fg-subtle">
        {icon}{label}
      </div>
      <div className="text-fg font-semibold text-base mt-0.5">{value}</div>
      {sub && <div className="text-[11px] text-fg-subtle truncate">{sub}</div>}
    </div>
  );
}
