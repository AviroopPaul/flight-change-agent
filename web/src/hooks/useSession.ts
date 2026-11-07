import { useEffect, useState } from "react";
import { initialSessionId, type Server } from "../config";

export interface SessionInfo {
  sessionId: string | null;
  error: string | null;
}

/** Uses ?sessionId= from the URL, or creates a session on the backend and writes its id into the URL. */
export function useSession(server: Server | null): SessionInfo {
  const [info, setInfo] = useState<SessionInfo>({ sessionId: initialSessionId, error: null });

  useEffect(() => {
    if (!server || info.sessionId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${server.http}/sessions`, { method: "POST" });
        const body = await res.json().catch(() => ({}));
        if (!res.ok || !body.sessionId) {
          if (!cancelled) setInfo({ sessionId: null, error: body.error ?? "Could not start a session. Please reload." });
          return;
        }
        const params = new URLSearchParams(location.search);
        params.set("sessionId", body.sessionId);
        history.replaceState(null, "", `${location.pathname}?${params}${location.hash}`);
        if (!cancelled) setInfo({ sessionId: body.sessionId, error: null });
      } catch {
        if (!cancelled) setInfo({ sessionId: null, error: `Can't reach the server at ${server.http}. Please reload.` });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [server, info.sessionId]);

  return info;
}
