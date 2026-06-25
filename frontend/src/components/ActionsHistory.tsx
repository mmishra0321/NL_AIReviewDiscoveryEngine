import { useEffect, useState } from "react";
import {
  Activity, CheckCircle2, XCircle, Clock, Download, ExternalLink,
  FileText, FileJson, Database, AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import type { ActionRun, ActionsResponse, RunStatus } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { cn, formatRelativeTime } from "@/lib/utils";

export function ActionsHistory() {
  const [data, setData] = useState<ActionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    (async () => {
      try { setData(await api.actions(10)); }
      catch (e) { setError((e as Error).message); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) {
    return (
      <Card>
        <CardContent className="p-5 space-y-2">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-16 w-full rounded-lg" />
        </CardContent>
      </Card>
    );
  }
  if (error) {
    return (
      <Card>
        <CardContent className="p-4 text-sm text-amber-300 flex gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-none" />
          Could not load Actions history: {error}
        </CardContent>
      </Card>
    );
  }
  if (!data) return null;

  const visible = expanded ? data.runs : data.runs.slice(0, 1);

  return (
    <Card>
      <CardContent className="p-5 md:p-6 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-brand" />
            <h3 className="text-base font-semibold text-fg">Weekly refresh history</h3>
            <span className="text-[11px] text-fg-subtle">cron, every Mon 02:00 UTC</span>
          </div>
          <a
            href={data.actions_tab_url}
            target="_blank"
            rel="noreferrer"
            className="text-[11px] text-fg-muted hover:text-fg inline-flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" /> view all on GitHub
          </a>
        </div>

        <div className="space-y-2">
          {visible.length === 0 && (
            <div className="text-sm text-fg-muted italic">No runs found.</div>
          )}
          {visible.map((r, idx) => <RunRow key={r.id ?? `idx-${idx}`} run={r} primary={idx === 0} />)}
        </div>

        {data.runs.length > 1 && (
          <button
            onClick={() => setExpanded((b) => !b)}
            className="text-[11px] text-fg-muted hover:text-fg"
          >
            {expanded
              ? `Hide ${data.runs.length - 1} older runs`
              : `Show ${data.runs.length - 1} older runs`}
          </button>
        )}
      </CardContent>
    </Card>
  );
}

function RunRow({ run, primary }: { run: ActionRun; primary: boolean }) {
  return (
    <div className={cn(
      "rounded-lg border bg-bg-subtle/40 px-3.5 py-3",
      primary ? "border-brand/40" : "border-border",
    )}>
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={run.status} />
        <span className="text-sm text-fg font-medium">{run.title}</span>
        <span className="text-[11px] text-fg-subtle inline-flex items-center gap-1">
          <Clock className="w-3 h-3" /> {formatRelativeTime(run.started_at)}
          {run.started_at && (
            <span className="text-fg-subtle/70 hidden md:inline">
              ({new Date(run.started_at).toUTCString()})
            </span>
          )}
        </span>
        {run.output_sha && (
          <span className="font-mono text-[11px] text-fg-subtle">
            #{run.output_sha.slice(0, 7)}
          </span>
        )}
        {run.html_url && (
          <a
            href={run.html_url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto text-[11px] text-fg-muted hover:text-fg inline-flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" /> view run
          </a>
        )}
      </div>

      {run.downloads && (
        <div className="flex flex-wrap items-center gap-2 mt-2.5">
          <span className="text-[11px] text-fg-subtle">Download data from this run:</span>
          <DownloadLink href={run.downloads.reviews_jsonl}      filename={`reviews-${shortSha(run.output_sha)}.jsonl`}     icon={<FileText className="w-3 h-3" />} label="reviews.jsonl" />
          <DownloadLink href={run.downloads.metadata}           filename={`metadata-${shortSha(run.output_sha)}.json`}     icon={<FileJson className="w-3 h-3" />} label="metadata.json" />
          <DownloadLink href={run.downloads.canonical_answers}  filename={`canonical-${shortSha(run.output_sha)}.json`}    icon={<FileJson className="w-3 h-3" />} label="canonical answers" />
          <DownloadLink href={run.downloads.seed_reviews}       filename={`seeds-${shortSha(run.output_sha)}.jsonl`}       icon={<Database className="w-3 h-3" />} label="seeds" />
        </div>
      )}
      {!run.downloads && run.status !== "success" && run.status !== "no_action_yet" && (
        <div className="text-[11px] text-fg-subtle mt-2 italic">
          No downloadable output (run did not produce a commit).
        </div>
      )}
    </div>
  );
}

function shortSha(sha: string | null): string {
  return (sha ?? "unknown").slice(0, 7);
}

function StatusBadge({ status }: { status: RunStatus }) {
  const map: Record<RunStatus, { label: string; cls: string; icon: React.ReactNode }> = {
    success:        { label: "success",        cls: "bg-brand/15 text-brand border-brand/40",          icon: <CheckCircle2 className="w-3 h-3" /> },
    failure:        { label: "failed",         cls: "bg-red-500/15 text-red-300 border-red-500/30",    icon: <XCircle      className="w-3 h-3" /> },
    cancelled:      { label: "cancelled",      cls: "bg-bg-subtle text-fg-muted border-border",        icon: <XCircle      className="w-3 h-3" /> },
    skipped:        { label: "skipped",        cls: "bg-bg-subtle text-fg-muted border-border",        icon: <XCircle      className="w-3 h-3" /> },
    pending:        { label: "running",        cls: "bg-amber-500/15 text-amber-300 border-amber-500/30", icon: <Clock      className="w-3 h-3" /> },
    no_action_yet:  { label: "initial commit", cls: "bg-blue-500/15 text-blue-300 border-blue-500/30", icon: <Activity     className="w-3 h-3" /> },
  };
  const m = map[status];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium", m.cls)}>
      {m.icon}{m.label}
    </span>
  );
}

function DownloadLink({
  href, filename, icon, label,
}: { href: string; filename: string; icon: React.ReactNode; label: string }) {
  return (
    <a href={href} download={filename} target="_blank" rel="noreferrer">
      <Button variant="outline" size="sm">
        <Download className="w-3 h-3" /> {icon} {label}
      </Button>
    </a>
  );
}
