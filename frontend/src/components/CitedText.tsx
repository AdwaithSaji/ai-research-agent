const MARKER_SPLIT_RE = /(\[\d+\])/g;
const MARKER_TEST_RE = /^\[\d+\]$/;

/** Renders text, turning [n] citation markers into jump links to the source list. */
export function CitedText({ text }: { text: string }) {
  const parts = text.split(MARKER_SPLIT_RE);
  return (
    <>
      {parts.map((part, i) =>
        MARKER_TEST_RE.test(part) ? (
          <a key={i} href={`#source-${part.replace(/[[\]]/g, "")}`} className="citation-marker">
            {part}
          </a>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}
