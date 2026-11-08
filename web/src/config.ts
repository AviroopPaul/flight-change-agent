export interface Server {
  http: string;
  ws: string;
}

const DEFAULT_DEMO_PACE = 1.5;

function parseServer(raw: string): Server | null {
  if (!raw) return null;
  try {
    const url = new URL(raw.includes("://") ? raw : `http://${raw}`);
    const secure = url.protocol === "https:" || url.protocol === "wss:";
    const hostPath = url.host + url.pathname.replace(/\/+$/, "");
    return { http: `${secure ? "https" : "http"}://${hostPath}`, ws: `${secure ? "wss" : "ws"}://${hostPath}` };
  } catch {
    return null;
  }
}

function describeServer(): string {
  if (demo) return "demo mode (no server)";
  return server ? `server ${server.http}` : "no server";
}

function describeSetupProblem(): string | null {
  if (demo || server) return null;
  return rawServer
    ? `Could not parse VITE_SERVER_URL "${rawServer}". Use e.g. http://localhost:8080`
    : "No backend configured. Set VITE_SERVER_URL in .env.local (see .env.example) and restart npm run dev to connect to your server, or open ?demo=1 to see the intended flow.";
}

const params = new URLSearchParams(location.search);
const pace = Number(params.get("pace"));
const rawServer = import.meta.env.VITE_SERVER_URL?.trim() ?? "";

/** The session id in the URL, if any. useSession creates one on the backend otherwise. */
export const initialSessionId = params.get("sessionId");

/** The session id in the URL right now (useSession writes it there). */
export const currentSessionId = (): string => new URLSearchParams(location.search).get("sessionId") ?? "";
/** This page without ?sessionId=, so loading it starts a new session. Other params (demo, pace) stay. */
export function newChatUrl(): string {
  const next = new URLSearchParams(location.search);
  next.delete("sessionId");
  const query = next.toString();
  return `${location.pathname}${query ? `?${query}` : ""}`;
}
export const demo = params.get("demo") === "1";
export const demoPace = pace > 0 ? pace : DEFAULT_DEMO_PACE;
export const server = parseServer(rawServer);
export const backend = demo ? null : server;
export const serverLabel = describeServer();
export const setupProblem = describeSetupProblem();
