import { useState } from "react";
import { Star, ExternalLink, ChevronDown } from "lucide-react";
import type { ReviewDTO } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { cn, sourceColor, sourceLabel } from "@/lib/utils";

export function ReviewList({
  reviews,
  pageSize = 5,
}: {
  reviews: ReviewDTO[];
  pageSize?: number;
}) {
  const [shown, setShown] = useState(pageSize);
  if (!reviews.length) {
    return <div className="text-sm text-fg-muted italic">No supporting reviews retrieved.</div>;
  }
  const visible = reviews.slice(0, shown);
  const hasMore = shown < reviews.length;

  return (
    <div className="space-y-2.5">
      {visible.map((r) => <ReviewItem key={r.id} r={r} />)}
      {hasMore && (
        <div className="pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShown((n) => Math.min(reviews.length, n + pageSize))}
          >
            <ChevronDown className="w-3.5 h-3.5" />
            View {Math.min(pageSize, reviews.length - shown)} more
            <span className="text-fg-subtle ml-1">({shown} / {reviews.length})</span>
          </Button>
        </div>
      )}
      {!hasMore && reviews.length > pageSize && (
        <div className="text-[11px] text-fg-subtle pt-1">Showing all {reviews.length} supporting reviews.</div>
      )}
    </div>
  );
}

function ReviewItem({ r }: { r: ReviewDTO }) {
  return (
    <div className="rounded-lg border border-border bg-bg-subtle/40 px-3.5 py-2.5 animate-slide-up">
      <div className="flex flex-wrap items-center gap-1.5 text-[11px] mb-1.5">
        <span className={cn("inline-flex items-center rounded-md border px-1.5 py-0.5 font-medium", sourceColor(r.source))}>
          {sourceLabel(r.source)}
        </span>
        {r.rating != null && (
          <span className="inline-flex items-center gap-0.5 text-amber-300">
            {Array.from({ length: 5 }).map((_, i) => (
              <Star key={i} className={cn("w-3 h-3",
                i < (r.rating ?? 0) ? "fill-amber-400 text-amber-400" : "text-fg-subtle")} />
            ))}
          </span>
        )}
        {r.author && <span className="text-fg-subtle">· {r.author}</span>}
        {r.locale && <span className="chip text-[10px]">{r.locale}</span>}
        {r.features_mentioned?.slice(0, 4).map((f) => (
          <span key={f} className="chip text-brand border-brand/30 bg-brand/10">{f}</span>
        ))}
        {r.url && (
          <a href={r.url} target="_blank" rel="noreferrer"
             className="ml-auto inline-flex items-center gap-0.5 text-fg-subtle hover:text-fg">
            <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
      <p className="text-[13.5px] leading-relaxed text-fg/90 whitespace-pre-wrap">{r.text}</p>
    </div>
  );
}
