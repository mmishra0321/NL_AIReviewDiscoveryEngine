import { useEffect, useState } from "react";
import { ArrowUpRight, MessageSquareQuote } from "lucide-react";
import { api } from "@/lib/api";
import type { CanonicalDetail, CanonicalList, CanonicalSummary } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn, confidenceColor } from "@/lib/utils";
import { AnswerPanel } from "@/components/AnswerPanel";

export function CanonicalGrid() {
  const [list, setList] = useState<CanonicalList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CanonicalDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try { setList(await api.canonical()); }
      catch (e) { setError((e as Error).message); }
      finally { setLoading(false); }
    })();
  }, []);

  useEffect(() => {
    if (!openId) { setDetail(null); return; }
    setDetailLoading(true);
    setDetail(null);
    api.canonicalDetail(openId)
      .then(setDetail)
      .catch((e) => setError((e as Error).message))
      .finally(() => setDetailLoading(false));
  }, [openId]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-44 rounded-xl" />)}
      </div>
    );
  }
  if (error) {
    return <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-300">{error}</div>;
  }
  if (!list) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {list.items.map((q) => (
          <QuestionCard key={q.id} q={q} open={openId === q.id} onOpen={() => setOpenId(q.id === openId ? null : q.id)} />
        ))}
      </div>

      {openId && (
        <Card className="border-brand/30 shadow-glow">
          <CardContent className="p-5 md:p-6">
            {detailLoading || !detail ? (
              <div className="space-y-3">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
              </div>
            ) : (
              <AnswerPanel
                title={detail.id}
                question={detail.full}
                answer={detail.answer}
                confidence={detail.confidence}
                features={detail.spotify_features_mentioned}
                segments={detail.user_segments_affected}
                reviews={detail.reviews}
              />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function QuestionCard({ q, open, onOpen }: { q: CanonicalSummary; open: boolean; onOpen: () => void }) {
  return (
    <Card interactive onClick={onOpen} className={cn(open && "border-brand/60 shadow-glow")}>
      <CardHeader className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-fg-subtle">{q.id}</div>
          <CardTitle className="mt-0.5">{q.short}</CardTitle>
        </div>
        <ArrowUpRight className={cn("w-4 h-4 text-fg-muted transition", open && "text-brand rotate-45")} />
      </CardHeader>
      <CardContent>
        <p className="text-xs text-fg-muted leading-relaxed line-clamp-2">{q.full}</p>
        {q.preview && (
          <p className="text-[12.5px] text-fg/85 mt-3 leading-relaxed line-clamp-3">{q.preview}</p>
        )}
        <div className="flex items-center justify-between mt-3 text-[11px]">
          <span className="inline-flex items-center gap-1 text-fg-subtle">
            <MessageSquareQuote className="w-3 h-3" />
            {q.review_count} reviews
          </span>
          {q.confidence && (
            <span className={cn("inline-flex items-center rounded-md border px-1.5 py-0.5 font-medium",
              confidenceColor(q.confidence))}>
              {q.confidence}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
