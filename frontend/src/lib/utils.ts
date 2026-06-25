import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const diffSec = Math.round((Date.now() - t) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`;
  return `${Math.round(diffSec / 86400)}d ago`;
}

export function formatNumber(n: number | undefined | null): string {
  if (n === undefined || n === null) return "-";
  return n.toLocaleString("en-US");
}

export function sourceLabel(source: string): string {
  switch (source) {
    case "app_store":    return "App Store";
    case "play_store":   return "Play Store";
    case "youtube":      return "YouTube";
    case "reddit":       return "Reddit";
    case "trustpilot":   return "Trustpilot";
    case "community":    return "Community";
    case "curated_seed": return "Seed";
    default:             return source;
  }
}

export function sourceColor(source: string): string {
  switch (source) {
    case "app_store":    return "bg-blue-500/15 text-blue-300 border-blue-500/30";
    case "play_store":   return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
    case "youtube":      return "bg-red-500/15 text-red-300 border-red-500/30";
    case "reddit":       return "bg-orange-500/15 text-orange-300 border-orange-500/30";
    case "trustpilot":   return "bg-teal-500/15 text-teal-300 border-teal-500/30";
    case "curated_seed": return "bg-purple-500/15 text-purple-300 border-purple-500/30";
    default:             return "bg-bg-subtle text-fg-muted border-border";
  }
}

export function confidenceColor(c: string | undefined | null): string {
  switch (c) {
    case "high":   return "bg-brand/15 text-brand border-brand/40";
    case "medium": return "bg-amber-500/15 text-amber-300 border-amber-500/30";
    case "low":    return "bg-red-500/15 text-red-300 border-red-500/30";
    default:       return "bg-bg-subtle text-fg-muted border-border";
  }
}
