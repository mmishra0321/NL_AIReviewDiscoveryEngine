import { useState } from "react";
import { Send, AlertCircle, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { AskResponse } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { AnswerPanel } from "@/components/AnswerPanel";

const SAMPLES = [
  "Why does Spotify keep recommending songs I already love?",
  "How do regional listeners feel about Discover Weekly?",
  "What do users say about the DJ feature?",
];

export function AskBox() {
  const [q, setQ] = useState("");
  const [resp, setResp] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(text?: string) {
    const question = (text ?? q).trim();
    if (!question) return;
    setLoading(true); setError(null); setResp(null);
    try {
      const r = await api.ask(question);
      setResp(r);
      if (text) setQ(text);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardContent className="p-5 md:p-6 space-y-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-brand" />
          <h2 className="text-base font-semibold text-fg">Ask a custom question</h2>
          <span className="text-[11px] text-fg-subtle ml-1">scope-checked · grounded in reviews</span>
        </div>

        <Textarea
          placeholder="Ask anything about Spotify discovery, recommendations, or repetitive listening…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void submit(); }
          }}
        />

        <div className="flex flex-wrap items-center gap-1.5">
          {SAMPLES.map((s) => (
            <button
              key={s}
              onClick={() => submit(s)}
              className="chip hover:bg-bg-hover hover:text-fg transition cursor-pointer max-w-md truncate">
              {s}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[11px] text-fg-subtle hidden md:inline">Ctrl/⌘ + Enter</span>
            <Button variant="primary" size="sm" onClick={() => submit()} disabled={loading || !q.trim()}>
              <Send className="w-3.5 h-3.5" /> {loading ? "Thinking…" : "Ask"}
            </Button>
          </div>
        </div>

        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-300 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5" /> {error}
          </div>
        )}

        {loading && (
          <div className="space-y-3 pt-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-24 w-full rounded-md" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        )}

        {resp && <ResponseView resp={resp} q={q} />}
      </CardContent>
    </Card>
  );
}

function ResponseView({ resp, q }: { resp: AskResponse; q: string }) {
  if (!resp.in_scope) {
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 animate-fade-in">
        <div className="flex items-start gap-2 text-amber-300">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-none" />
          <div className="space-y-2">
            <div className="text-sm font-semibold">Out of scope</div>
            <p className="text-[13px] text-amber-100/90 leading-relaxed">{resp.message}</p>
            <p className="text-[11px] text-fg-subtle">
              Scope check: <span className="text-fg-muted">{resp.scope_confidence}</span>
              {" · "}similarity <span className="text-fg-muted">{resp.max_similarity.toFixed(2)}</span>
              {" · "}reason <span className="text-fg-muted italic">{resp.reason}</span>
            </p>
          </div>
        </div>
      </div>
    );
  }
  if (resp.answer == null) {
    return (
      <div className="rounded-lg border border-border bg-bg-subtle p-4 text-sm text-fg-muted">
        {resp.error ?? "No answer."}
      </div>
    );
  }
  return (
    <AnswerPanel
      question={q}
      answer={resp.answer}
      confidence={resp.confidence}
      features={resp.spotify_features_mentioned}
      segments={resp.user_segments_affected}
      reviews={resp.reviews}
    />
  );
}
