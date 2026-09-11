import type { ResearchJob, ResearchRequest, ProgressEvent } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function startResearch(request: ResearchRequest): Promise<ResearchJob> {
  const resp = await fetch(`${API_BASE}/api/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const detail = Array.isArray(body?.detail)
      ? body.detail.map((d: { msg?: string }) => d.msg).join(", ")
      : body?.detail;
    throw new ApiError(detail || `Request failed (${resp.status})`, resp.status);
  }
  return resp.json();
}

export async function getResearch(jobId: string): Promise<ResearchJob> {
  const resp = await fetch(`${API_BASE}/api/research/${jobId}`);
  if (!resp.ok) {
    throw new ApiError(`Failed to fetch research job (${resp.status})`, resp.status);
  }
  return resp.json();
}

export interface StreamHandlers {
  onProgress: (event: ProgressEvent) => void;
  onComplete: (job: ResearchJob) => void;
  onError: (error: string) => void;
}

/** Subscribes to the SSE progress stream for a research job. Returns a cleanup function. */
export function streamResearch(jobId: string, handlers: StreamHandlers): () => void {
  const source = new EventSource(`${API_BASE}/api/research/${jobId}/stream`);

  source.addEventListener("progress", (evt) => {
    try {
      handlers.onProgress(JSON.parse((evt as MessageEvent).data));
    } catch {
      /* ignore malformed event */
    }
  });

  source.addEventListener("complete", (evt) => {
    try {
      handlers.onComplete(JSON.parse((evt as MessageEvent).data));
    } catch {
      handlers.onError("Failed to parse final report from server.");
    }
    source.close();
  });

  source.onerror = () => {
    // EventSource auto-retries; if the job is actually gone the caller's
    // polling fallback (see useResearch) will surface the real error.
  };

  return () => source.close();
}
