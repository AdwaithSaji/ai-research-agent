import { useCallback, useRef, useState } from "react";
import { ApiError, getResearch, startResearch, streamResearch } from "../api/client";
import type { ProgressEvent, ResearchJob, ResearchRequest } from "../types";

export type ResearchStatus = "idle" | "submitting" | "running" | "done" | "error";

interface ResearchState {
  status: ResearchStatus;
  job: ResearchJob | null;
  events: ProgressEvent[];
  error: string | null;
}

const initialState: ResearchState = { status: "idle", job: null, events: [], error: null };

export function useResearch() {
  const [state, setState] = useState<ResearchState>(initialState);
  const cleanupRef = useRef<() => void>(() => {});

  const reset = useCallback(() => {
    cleanupRef.current();
    setState(initialState);
  }, []);

  const submit = useCallback(async (request: ResearchRequest) => {
    cleanupRef.current();
    setState({ status: "submitting", job: null, events: [], error: null });

    let job: ResearchJob;
    try {
      job = await startResearch(request);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to start research.";
      setState({ status: "error", job: null, events: [], error: message });
      return;
    }

    setState({ status: "running", job, events: [], error: null });

    const finish = async () => {
      try {
        const finalJob = await getResearch(job.id);
        if (finalJob.stage === "failed") {
          setState((s) => ({ ...s, status: "error", job: finalJob, error: finalJob.error }));
        } else {
          setState((s) => ({ ...s, status: "done", job: finalJob }));
        }
      } catch {
        setState((s) => ({ ...s, status: "error", error: "Lost connection to the research job." }));
      }
    };

    cleanupRef.current = streamResearch(job.id, {
      onProgress: (event) => {
        setState((s) => ({ ...s, events: [...s.events, event] }));
      },
      onComplete: (finalJob) => {
        if (finalJob.stage === "failed") {
          setState((s) => ({ ...s, status: "error", job: finalJob, error: finalJob.error }));
        } else {
          setState((s) => ({ ...s, status: "done", job: finalJob }));
        }
      },
      onError: () => {
        void finish();
      },
    });
  }, []);

  return { ...state, submit, reset };
}
