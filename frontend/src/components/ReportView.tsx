import { CitedText } from "./CitedText";
import { SourceCard } from "./SourceCard";
import type { ResearchReport, UsageStats } from "../types";

interface Props {
  report: ResearchReport;
  usage: UsageStats;
}

export function ReportView({ report, usage }: Props) {
  const sourceById = new Map(report.sources.map((s) => [s.id, s]));
  const markerBySourceId = new Map(report.citations.map((c) => [c.source_id, c.marker]));

  return (
    <div className="report-view">
      <UsageBar usage={usage} />

      {report.insufficient_evidence && (
        <div className="banner banner-warning">
          <strong>Insufficient evidence.</strong> This system could not find enough verified,
          relevant source material to confidently answer the question. Treat the content below as
          incomplete rather than a definitive answer.
        </div>
      )}

      <section className="report-section">
        <h2>Executive Summary</h2>
        <p>
          <CitedText text={report.executive_summary} />
        </p>
      </section>

      <section className="report-section">
        <h2>Research Question</h2>
        <p className="research-question-text">{report.question}</p>
      </section>

      <section className="report-section">
        <h2>Methodology</h2>
        <p className="methodology-text">{report.methodology}</p>
      </section>

      {report.key_findings.length > 0 && (
        <section className="report-section">
          <h2>Key Findings</h2>
          <ul className="findings-list">
            {report.key_findings.map((f, i) => (
              <li key={i}>
                <CitedText text={f} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.evidence_summary.length > 0 && (
        <section className="report-section">
          <h2>Evidence</h2>
          {report.evidence_summary.map((sec, i) => (
            <div key={i} className="evidence-group">
              <h3>{sec.heading}</h3>
              <div className="evidence-content">
                <CitedText text={sec.content} />
              </div>
            </div>
          ))}
        </section>
      )}

      <section className="report-section">
        <h2>Conflicting Evidence</h2>
        {report.conflicting_evidence.length === 0 ? (
          <p className="muted">No conflicting evidence was detected among the sources reviewed.</p>
        ) : (
          <ul className="conflicts-list">
            {report.conflicting_evidence.map((c, i) => (
              <li key={i} className="conflict-item">
                <strong>{c.topic}</strong>
                <p>{c.description}</p>
                <div className="conflict-sources">
                  {c.source_ids.map((sid) => {
                    const marker = markerBySourceId.get(sid);
                    const source = sourceById.get(sid);
                    return marker && source ? (
                      <a key={sid} href={`#source-${marker.replace(/[[\]]/g, "")}`} className="citation-marker">
                        {marker} {source.domain}
                      </a>
                    ) : null;
                  })}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="report-section">
        <h2>Analysis</h2>
        <p>
          <CitedText text={report.analysis} />
        </p>
      </section>

      <section className="report-section">
        <h2>Uncertainty &amp; Research Gaps</h2>
        <p className="uncertainty-text">{report.uncertainty}</p>
      </section>

      <section className="report-section">
        <h2>Conclusion</h2>
        <p>{report.conclusion}</p>
      </section>

      <section className="report-section">
        <h2>Sources ({report.sources.length})</h2>
        {report.sources.length === 0 ? (
          <p className="muted">No sources were retained for this report.</p>
        ) : (
          <div className="sources-grid">
            {report.sources.map((s) => (
              <div key={s.id} id={`source-${markerBySourceId.get(s.id)?.replace(/[[\]]/g, "") ?? s.id}`}>
                <SourceCard source={s} marker={markerBySourceId.get(s.id)} />
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function UsageBar({ usage }: { usage: UsageStats }) {
  return (
    <div className="usage-bar">
      <Stat label="Searches" value={usage.searches_performed} />
      <Stat label="Sources found" value={usage.sources_retrieved} />
      <Stat label="Sources used" value={usage.sources_used} />
      <Stat label="LLM calls" value={usage.llm_calls} />
      <Stat label="Duration" value={`${usage.duration_seconds.toFixed(1)}s`} />
      <Stat label="Est. cost" value={`$${usage.estimated_cost_usd.toFixed(4)}`} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
