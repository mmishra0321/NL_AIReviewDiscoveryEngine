import { cn } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: "neutral" | "brand" | "warn" | "danger" | "info";
}

const tones: Record<NonNullable<BadgeProps["tone"]>, string> = {
  neutral: "bg-bg-subtle text-fg-muted border-border",
  brand:   "bg-brand/15 text-brand border-brand/40",
  warn:    "bg-amber-500/15 text-amber-300 border-amber-500/30",
  danger:  "bg-red-500/15 text-red-300 border-red-500/30",
  info:    "bg-blue-500/15 text-blue-300 border-blue-500/30",
};

export function Badge({ className, tone = "neutral", ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium",
        tones[tone],
        className,
      )}
      {...rest}
    />
  );
}
