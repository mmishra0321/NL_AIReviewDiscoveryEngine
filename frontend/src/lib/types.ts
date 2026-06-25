// Mirrors the Pydantic shapes returned by the FastAPI backend.

export interface Health {
  ok: boolean;
  version: string;
  last_refresh_utc: string | null;
  total_normalized: number;
  total_relevant: number;
}

export interface Meta {
  last_refresh_utc: string | null;
  total_normalized: number;
  total_relevant: number;
  by_source: Record<string, number>;
  by_canonical_tag: Record<string, number>;
  feature_mention_counts: Record<string, number>;
  scrape_counts_this_run: Record<string, number>;
  chroma_collection_size: number;
}

export type Confidence = "high" | "medium" | "low";

export interface ReviewDTO {
  id: string;
  source: string;
  text: string;
  rating: number | null;
  author: string | null;
  date: string | null;
  url: string | null;
  locale: string | null;
  features_mentioned: string[];
  canonical_tags: string[];
  user_segments: string[];
}

export interface CanonicalSummary {
  id: string;
  short: string;
  full: string;
  description: string;
  has_answer: boolean;
  confidence: Confidence | null;
  preview: string | null;
  review_count: number;
  spotify_features_mentioned: string[];
  user_segments_affected: string[];
}

export interface CanonicalList {
  generated_at: string | null;
  items: CanonicalSummary[];
}

export interface CanonicalDetail {
  id: string;
  short: string;
  full: string;
  description: string;
  answer: string;
  spotify_features_mentioned: string[];
  user_segments_affected: string[];
  confidence: Confidence;
  reviews: ReviewDTO[];
}

export interface AskResponseInScope {
  in_scope: true;
  scope_confidence: string;
  max_similarity: number;
  nearest_canonical_id: string;
  question?: string;
  answer: string | null;
  spotify_features_mentioned: string[];
  user_segments_affected: string[];
  confidence: Confidence;
  reviews: ReviewDTO[];
  error?: string;
}

export interface AskResponseOutOfScope {
  in_scope: false;
  scope_confidence: string;
  max_similarity: number;
  nearest_canonical_id: string;
  reason: string;
  message: string;
}

export type AskResponse = AskResponseInScope | AskResponseOutOfScope;
