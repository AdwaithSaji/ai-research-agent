import { useState, type FormEvent } from "react";
import type { ResearchDepth, ResearchRequest } from "../types";

interface Props {
  disabled: boolean;
  onSubmit: (request: ResearchRequest) => void;
}

const DEPTH_OPTIONS: { value: ResearchDepth; label: string; hint: string }[] = [
  { value: "quick", label: "Quick", hint: "2 subquestions · fastest" },
  { value: "standard", label: "Standard", hint: "3 subquestions · balanced" },
  { value: "deep", label: "Deep", hint: "4 subquestions · most thorough" },
];

export function ResearchForm({ disabled, onSubmit }: Props) {
  const [question, setQuestion] = useState("");
  const [depth, setDepth] = useState<ResearchDepth>("standard");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [preferredDomains, setPreferredDomains] = useState("");
  const [excludedDomains, setExcludedDomains] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (trimmed.length < 8) {
      setValidationError("Please enter a more complete research question (at least 8 characters).");
      return;
    }
    setValidationError(null);
    onSubmit({
      question: trimmed,
      depth,
      preferred_domains: splitDomains(preferredDomains),
      excluded_domains: splitDomains(excludedDomains),
    });
  }

  return (
    <form className="research-form" onSubmit={handleSubmit}>
      <label className="field-label" htmlFor="question">
        Research question
      </label>
      <textarea
        id="question"
        className="question-input"
        placeholder="e.g. Compare current approaches for reducing hallucinations in large language models"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        disabled={disabled}
        rows={3}
        maxLength={500}
      />
      {validationError && <p className="field-error">{validationError}</p>}

      <div className="depth-selector" role="radiogroup" aria-label="Research depth">
        {DEPTH_OPTIONS.map((opt) => (
          <button
            type="button"
            key={opt.value}
            className={`depth-option${depth === opt.value ? " active" : ""}`}
            onClick={() => setDepth(opt.value)}
            disabled={disabled}
            aria-pressed={depth === opt.value}
          >
            <span className="depth-label">{opt.label}</span>
            <span className="depth-hint">{opt.hint}</span>
          </button>
        ))}
      </div>

      <button
        type="button"
        className="advanced-toggle"
        onClick={() => setShowAdvanced((v) => !v)}
        disabled={disabled}
      >
        {showAdvanced ? "Hide" : "Show"} source preferences
      </button>

      {showAdvanced && (
        <div className="advanced-fields">
          <div className="field-group">
            <label className="field-label" htmlFor="preferred">
              Preferred domains (comma-separated)
            </label>
            <input
              id="preferred"
              type="text"
              placeholder="e.g. arxiv.org, nature.com"
              value={preferredDomains}
              onChange={(e) => setPreferredDomains(e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="field-group">
            <label className="field-label" htmlFor="excluded">
              Excluded domains (comma-separated)
            </label>
            <input
              id="excluded"
              type="text"
              placeholder="e.g. pinterest.com"
              value={excludedDomains}
              onChange={(e) => setExcludedDomains(e.target.value)}
              disabled={disabled}
            />
          </div>
        </div>
      )}

      <button type="submit" className="submit-button" disabled={disabled}>
        {disabled ? "Researching…" : "Start research"}
      </button>
    </form>
  );
}

function splitDomains(value: string): string[] {
  return value
    .split(",")
    .map((d) => d.trim().toLowerCase())
    .filter(Boolean)
    .slice(0, 10);
}
