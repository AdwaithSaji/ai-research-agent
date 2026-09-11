import type { ProgressEvent, Stage } from "../types";

const STAGES: { key: Stage; label: string }[] = [
  { key: "planning", label: "Planning" },
  { key: "searching", label: "Searching" },
  { key: "analyzing", label: "Analyzing" },
  { key: "verifying", label: "Verifying" },
  { key: "synthesizing", label: "Synthesizing" },
];

interface Props {
  events: ProgressEvent[];
  currentStage: Stage;
  error: string | null;
}

export function ProgressView({ events, currentStage, error }: Props) {
  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);
  const sourcesFound = [...events].reverse().find((e) => e.sources_found > 0)?.sources_found ?? 0;
  const latestMessage = events.at(-1)?.message;

  return (
    <div className="progress-view">
      <ol className="stage-timeline">
        {STAGES.map((stage, i) => {
          const state =
            error && i === currentIndex
              ? "failed"
              : currentIndex > i || currentStage === "done"
                ? "done"
                : currentIndex === i
                  ? "active"
                  : "pending";
          return (
            <li key={stage.key} className={`stage-item stage-${state}`}>
              <span className="stage-dot" aria-hidden />
              <span className="stage-name">{stage.label}</span>
            </li>
          );
        })}
      </ol>

      <div className="progress-detail">
        {error ? (
          <p className="progress-error">⚠ {error}</p>
        ) : (
          <p className="progress-message">{latestMessage ?? "Starting…"}</p>
        )}
        {sourcesFound > 0 && (
          <p className="progress-sources">{sourcesFound} source(s) found so far</p>
        )}
      </div>

      <div className="progress-log">
        {events.map((e, i) => (
          <div key={i} className="progress-log-item">
            <span className={`log-stage log-stage-${e.stage}`}>{e.stage}</span>
            <span className="log-message">{e.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
