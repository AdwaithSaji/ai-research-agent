// Mirrors backend/app/models/schemas.py — keep in sync manually (small,
// stable contract; not worth a codegen step for this project's scope).

export type ResearchDepth = "quick" | "standard" | "deep";

export interface ResearchRequest {
  question: string;
  depth: ResearchDepth;
  preferred_domains: string[];
  excluded_domains: string[];
}

export type Stage =
  | "queued"
  | "planning"
  | "searching"
  | "analyzing"
  | "verifying"
  | "synthesizing"
  | "done"
  | "failed";

export type SourceType =
  | "academic"
  | "government"
  | "news"
  | "organization"
  | "blog"
  | "documentation"
  | "other";

export interface Source {
  id: string;
  title: string;
  url: string;
  domain: string;
  publisher: string;
  source_type: SourceType;
  retrieved_at: string;
  snippet: string;
  content: string;
  fetch_ok: boolean;
  fetch_error: string | null;
  quality_score: number;
  relevance_score: number;
  query: string;
}

export interface Conflict {
  topic: string;
  description: string;
  source_ids: string[];
}

export interface Citation {
  marker: string;
  source_id: string;
}

export interface ReportSection {
  heading: string;
  content: string;
}

export interface ReportQualityStats {
  total_evidence_extracted: number;
  evidence_kept_after_verification: number;
  quotes_attempted: number;
  quotes_verified: number;
  citation_markers_found: number;
  citation_markers_valid: number;
  citation_markers_invalid_removed: number;
  quote_validity_rate: number | null;
  citation_validity_rate: number | null;
}

export interface ResearchReport {
  question: string;
  executive_summary: string;
  methodology: string;
  key_findings: string[];
  evidence_summary: ReportSection[];
  conflicting_evidence: Conflict[];
  analysis: string;
  uncertainty: string;
  conclusion: string;
  sources: Source[];
  citations: Citation[];
  insufficient_evidence: boolean;
  quality_stats: ReportQualityStats;
}

export interface UsageStats {
  searches_performed: number;
  queries_attempted: number;
  queries_with_results: number;
  sources_retrieved: number;
  sources_used: number;
  llm_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost_usd: number;
  duration_seconds: number;
  cache_hits: number;
}

export interface ProgressEvent {
  stage: Stage;
  message: string;
  sources_found: number;
  timestamp: string;
}

export interface ResearchJob {
  id: string;
  request: ResearchRequest;
  stage: Stage;
  created_at: string;
  updated_at: string;
  events: ProgressEvent[];
  report: ResearchReport | null;
  usage: UsageStats;
  error: string | null;
}
