import { useState } from "react";
import type { Source } from "../types";

const TYPE_LABELS: Record<string, string> = {
  academic: "Academic",
  government: "Government",
  news: "News",
  organization: "Organization",
  blog: "Blog",
  documentation: "Docs",
  other: "Other",
};

export function SourceCard({ source, marker }: { source: Source; marker?: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="source-card">
      <div className="source-card-header">
        {marker && <span className="source-marker">{marker}</span>}
        <a href={source.url} target="_blank" rel="noopener noreferrer" className="source-title">
          {source.title}
        </a>
      </div>
      <div className="source-meta">
        <span className={`type-badge type-${source.source_type}`}>
          {TYPE_LABELS[source.source_type] ?? source.source_type}
        </span>
        <span className="source-domain">{source.domain}</span>
        <span className="source-score" title="Heuristic source quality">
          quality {Math.round(source.quality_score * 100)}%
        </span>
        <span className="source-score" title="Lexical relevance to its subquestion">
          relevance {Math.round(source.relevance_score * 100)}%
        </span>
        {!source.fetch_ok && <span className="source-warning">fetch failed</span>}
      </div>
      {source.snippet && <p className="source-snippet">{source.snippet}</p>}
      {source.fetch_ok && source.content && (
        <button type="button" className="source-expand" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Hide extracted text" : "View extracted text"}
        </button>
      )}
      {expanded && <p className="source-content">{source.content.slice(0, 1500)}</p>}
      {!source.fetch_ok && source.fetch_error && (
        <p className="source-error">Could not retrieve this page: {source.fetch_error}</p>
      )}
    </div>
  );
}
