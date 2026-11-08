import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../lib/errors";
import { fetchTimeline, type Timeline } from "../lib/timeline";

const REFRESH_MS = 4000;

/** Loads the session timeline while the debug view is open, and refreshes it so a live call shows up. */
export function useTimeline(http: string | null, sessionId: string | null, open: boolean) {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!open || !http || !sessionId) return;
    const ctrl = new AbortController();
    fetchTimeline(http, sessionId, ctrl.signal)
      .then((t) => {
        setTimeline(t);
        setError(null);
      })
      .catch((err) => {
        if (!ctrl.signal.aborted) setError(errorMessage(err, "Could not load the timeline."));
      });
    const timer = setTimeout(refresh, REFRESH_MS);
    return () => {
      ctrl.abort();
      clearTimeout(timer);
    };
  }, [open, http, sessionId, tick, refresh]);

  return { timeline, error, refresh };
}
