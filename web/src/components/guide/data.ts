/**
 * What the presenter needs on screen while recording the demo. The bookings copy the test data in
 * backend/app/catalog/data/bookings.json; update both together.
 */

export type FareClass = "saver" | "flex";

export interface GuideBooking {
  pnr: string;
  passengers: string[];
  route: string;
  flightNo: string;
  fareClass: FareClass;
  farePerPax: number;
  /** Departure relative to now, as in the backend data. */
  departs: { days: number; time: string } | { hours: number };
  /** Set for bookings that exist to show a rejection. */
  blocked?: string;
}

export const BOOKINGS: GuideBooking[] = [
  { pnr: "ABC123", passengers: ["Rahul Sharma"], route: "BLR → DEL", flightNo: "AQ808", fareClass: "saver", farePerPax: 5400, departs: { days: 5, time: "07:05" } },
  { pnr: "PQR456", passengers: ["Ananya Iyer", "Kartik Iyer"], route: "BOM → DEL", flightNo: "AQ862", fareClass: "saver", farePerPax: 6100, departs: { days: 9, time: "18:40" } },
  { pnr: "FLX789", passengers: ["Meera Nair"], route: "BLR → BOM", flightNo: "AQ833", fareClass: "flex", farePerPax: 8900, departs: { days: 12, time: "09:35" } },
  { pnr: "CNX111", passengers: ["Arjun Mehta"], route: "DEL → CCU", flightNo: "AQ851", fareClass: "saver", farePerPax: 5000, departs: { days: 6, time: "11:15" }, blocked: "Cancelled" },
  { pnr: "OLD222", passengers: ["Sneha Rao"], route: "HYD → DEL", flightNo: "AQ866", fareClass: "saver", farePerPax: 4900, departs: { days: -2, time: "08:00" }, blocked: "Already flown" },
  { pnr: "SON333", passengers: ["Vikram Singh"], route: "BLR → DEL", flightNo: "AQ877", fareClass: "saver", farePerPax: 5200, departs: { hours: 2 }, blocked: "Leaves in 2 h" },
];

export const CHANGE_FEE: Record<FareClass, number> = { saver: 3000, flex: 0 };

export interface Scenario {
  id: string;
  title: string;
  /** The outcome on the final record, if the scenario ends in one. */
  outcome?: "completed" | "needsReview" | "optedOut" | "partial";
  cue: string;
}

export const SCENARIOS: Scenario[] = [
  { id: "happy", title: "Change a flight", outcome: "completed", cue: "ABC123, call and chat together" },
  { id: "invalid", title: "Bad inputs", cue: "CNX111, OLD222, SON333, a wrong name" },
  { id: "flex", title: "Flex fare", outcome: "completed", cue: "FLX789, no change fee" },
  { id: "chat-continues", title: "Call ends, chat continues", cue: "Hang up, answer the next card" },
  { id: "call-back", title: "Call me back", cue: "Agent resumes with full context" },
  { id: "call-drop", title: "Call drops", cue: "Reload mid-call, call again" },
  { id: "restart", title: "Server restarts", cue: "Redeploy, reload, nothing lost" },
  { id: "needs-review", title: "Refund instead", outcome: "needsReview", cue: "Ask for a refund" },
  { id: "opt-out", title: "Stop request", outcome: "optedOut", cue: "Stop request, then Yes" },
  { id: "partial", title: "Leave, then come back", outcome: "partial", cue: "PQR456, revision 2 on return" },
  { id: "debug", title: "Debug view", cue: "Timeline, tools, latency, cost" },
];
