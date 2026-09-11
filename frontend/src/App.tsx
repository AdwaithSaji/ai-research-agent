import { ProgressView } from "./components/ProgressView";
import { ReportView } from "./components/ReportView";
import { ResearchForm } from "./components/ResearchForm";
import { useResearch } from "./hooks/useResearch";

function App() {
  const { status, job, events, error, submit, reset } = useResearch();
  const isBusy = status === "submitting" || status === "running";

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <h1>AI Research Agent</h1>
          <p className="app-subtitle">
            Autonomous, citation-grounded research over multiple live web sources.
          </p>
        </div>
      </header>

      <main className="app-main">
        <section className="input-panel">
          <ResearchForm disabled={isBusy} onSubmit={submit} />
          {status !== "idle" && (
            <button className="reset-button" onClick={reset} disabled={isBusy && status === "submitting"}>
              {isBusy ? "Cancel view" : "New research"}
            </button>
          )}
        </section>

        <section className="output-panel">
          {status === "idle" && <EmptyState />}

          {(status === "submitting" || status === "running") && job && (
            <ProgressView events={events.length ? events : job.events} currentStage={job.stage} error={null} />
          )}

          {status === "error" && (
            <div className="error-panel">
              <h2>Something went wrong</h2>
              <p>{error ?? "An unknown error occurred."}</p>
              {job?.usage && job.usage.searches_performed > 0 && (
                <p className="muted">
                  Partial progress: {job.usage.sources_retrieved} source(s) retrieved before failure.
                </p>
              )}
            </div>
          )}

          {status === "done" && job?.report && <ReportView report={job.report} usage={job.usage} />}
        </section>
      </main>

      <footer className="app-footer">
        <p>
          Reports are generated from live web sources and may be incomplete. Always verify important
          claims against the cited sources.
        </p>
      </footer>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="empty-state">
      <h2>Ask a research question</h2>
      <p>
        Enter a question on the left — the agent will plan subquestions, search multiple sources,
        extract and verify evidence, and synthesize a cited report.
      </p>
      <ul className="empty-state-examples">
        <li>“Compare current approaches for reducing hallucinations in large language models.”</li>
        <li>“What are the tradeoffs between vector databases for retrieval-augmented generation?”</li>
        <li>“What is the current scientific consensus on intermittent fasting and longevity?”</li>
      </ul>
    </div>
  );
}

export default App;
