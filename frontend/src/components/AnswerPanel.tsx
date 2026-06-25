import { Sparkles, Users, Music2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { ReviewList } from "@/components/ReviewList";
import { cn, confidenceColor } from "@/lib/utils";
import type { Confidence, ReviewDTO } from "@/lib/types";

interface AnswerPanelProps {
  title?: string;
  question: string;
  answer: string;
  confidence?: Confidence;
  features?: string[];
  segments?: string[];
  reviews: ReviewDTO[];
}

export function AnswerPanel({
  title,
  question,
  answer,
  confidence,
  features = [],
  segments = [],
  reviews,
}: AnswerPanelProps) {
  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-start justify-between gap-3">
        <div>
          {title && <div className="text-[11px] uppercase tracking-wider text-fg-subtle">{title}</div>}
          <h3 className="text-lg font-semibold text-fg leading-tight">{question}</h3>
        </div>
        {confidence && (
          <span className={cn(
            "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium",
            confidenceColor(confidence),
          )}>
            <Sparkles className="w-3 h-3" /> {confidence} confidence
          </span>
        )}
      </div>

      <div className="rounded-lg border border-brand/30 bg-gradient-to-br from-brand/5 to-transparent p-4">
        <p className="text-[14.5px] leading-relaxed text-fg/95 whitespace-pre-wrap">{answer}</p>
      </div>

      {(features.length > 0 || segments.length > 0) && (
        <div className="flex flex-wrap gap-3 text-xs">
          {features.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <Music2 className="w-3.5 h-3.5 text-brand" />
              <span className="text-fg-subtle">Features:</span>
              {features.map((f) => <Badge key={f} tone="brand">{f}</Badge>)}
            </div>
          )}
          {segments.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-info" />
              <span className="text-fg-subtle">Segments:</span>
              {segments.map((s) => <Badge key={s} tone="info">{s}</Badge>)}
            </div>
          )}
        </div>
      )}

      <div>
        <div className="text-[11px] uppercase tracking-wider text-fg-subtle mb-2">
          Supporting reviews · {reviews.length}
        </div>
        <ReviewList reviews={reviews} pageSize={5} />
      </div>
    </div>
  );
}
