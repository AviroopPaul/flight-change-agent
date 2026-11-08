/** Turns the final record into short, readable rows. Pure; unknown shapes fall back to plain text. */
import { formatValue, isPlainObject, readField } from "./record";

export type RowIcon = "plane" | "ticket" | "user" | "calendar" | "clock" | "reason" | "mail" | "card" | "check";

export interface Row {
  key: string;
  icon: RowIcon;
  label: string;
  value: string;
  detail?: string;
  chip?: string;
  source?: string;
  flagged?: string;
  emphasis?: boolean;
}

export interface Section {
  title: string;
  rows: Row[];
}

type Obj = Record<string, unknown>;

const OPTIONAL = new Set(["contactEmail"]);

const FLEX: Record<string, string> = {
  morning: "Morning (5 am to 12 pm)",
  afternoon: "Afternoon (12 pm to 5 pm)",
  evening: "Evening (5 pm to midnight)",
  any: "Any time",
};

export const rupees = (n: unknown): string =>
  typeof n === "number" ? `₹${n.toLocaleString("en-IN")}` : formatValue(n);

export function dateLabel(iso: unknown): string {
  if (typeof iso !== "string" || iso.length < 10) return formatValue(iso);
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}

const timeOf = (iso: unknown): string => (typeof iso === "string" && iso.length >= 16 ? iso.slice(11, 16) : "");

const titleCase = (s: string): string => s.toLowerCase().replace(/\b\p{L}/gu, (c) => c.toUpperCase());

export function minutes(seconds: unknown): string {
  if (typeof seconds !== "number" || seconds <= 0) return "0 s";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m ? `${m} min ${s} s` : `${s} s`;
}

function row(fields: Obj, name: string, icon: RowIcon, label: string, show: (v: unknown) => Partial<Row>): Row {
  const { value, source, status, flagged } = readField(fields[name]);
  const missing = value === null || value === undefined || value === "";
  const base: Row = {
    key: name,
    icon,
    label,
    value: missing ? (status === "valid" ? "Skipped" : "Not given") : "",
    source: source ? String(source) : undefined,
    // An optional field left empty is not a problem, so it gets no red flag.
    flagged: flagged && !(missing && OPTIONAL.has(name)) ? String(status) : undefined,
  };
  return missing ? base : { ...base, ...show(value) };
}

export function recordSections(record: Obj): Section[] {
  const fields = isPlainObject(record.fields) ? record.fields : {};
  const quote = isPlainObject(record.quote) ? record.quote : null;
  const booking = isPlainObject(record.booking) ? record.booking : null;
  const refund = record.requestType === "refund";

  const trip: Row[] = [];
  if (!refund) {
    trip.push(row(fields, "selectedFlight", "plane", "New flight", (v) => {
      if (!isPlainObject(v)) return { value: formatValue(v) };
      const route = [v.origin, v.destination].filter(Boolean).join(" → ");
      return {
        value: `${formatValue(v.flightNo)} · ${route}`,
        detail: `${dateLabel(v.departure)} · ${timeOf(v.departure)} → ${timeOf(v.arrival)}`,
        emphasis: true,
      };
    }));
  }
  trip.push(row(fields, "pnr", "ticket", "Booking", (v) => ({
    value: String(v),
    detail: booking ? `${formatValue(booking.route).replace("-", " → ")} · was ${formatValue(booking.originalFlight)} on ${dateLabel(booking.originalDeparture)}` : undefined,
  })));
  trip.push(row(fields, "passengerNames", "user", "Passengers", (v) => ({
    value: (Array.isArray(v) ? v : [v]).map((n) => titleCase(String(n))).join(", "),
  })));

  const payment: Row[] = [];
  if (quote && !refund) {
    const due = typeof quote.amountDue === "number" && quote.amountDue > 0;
    const back = typeof quote.refundDue === "number" && quote.refundDue > 0;
    const accepted = readField(fields.fareAcceptance);
    payment.push({
      key: "fare",
      icon: "card",
      label: due ? "You pay" : back ? "Refund" : "Fare",
      value: due ? rupees(quote.amountDue) : back ? `${rupees(quote.refundDue)} to ${formatValue(quote.refundTo)}` : "Nothing to pay",
      detail: `New fare ${rupees(quote.newFare)} · old ${rupees(quote.oldFare)} · fee ${rupees(quote.changeFeePerPax)} per person`,
      source: accepted.source ? String(accepted.source) : undefined,
      chip: accepted.value ? "Accepted" : undefined,
      emphasis: true,
    });
  }

  const request: Row[] = [
    row(fields, "changeReason", "reason", "Reason", (v) => {
      if (!isPlainObject(v)) return { value: formatValue(v) };
      return { value: formatValue(v.text), chip: v.category ? titleCase(String(v.category)) : undefined };
    }),
  ];
  if (!refund) {
    request.push(row(fields, "newTravelDate", "calendar", "Travel date", (v) => ({ value: dateLabel(v) })));
    request.push(row(fields, "timeFlexibility", "clock", "Time of day", (v) => ({ value: FLEX[String(v)] ?? String(v) })));
    request.push(row(fields, "contactEmail", "mail", "E-ticket email", (v) => ({ value: String(v) })));
  }

  return [
    { title: refund ? "Booking" : "Trip", rows: trip },
    { title: "Payment", rows: payment },
    { title: "Request", rows: request },
  ].filter((s) => s.rows.length);
}

export function engagementLine(record: Obj): string {
  const e = isPlainObject(record.engagement) ? record.engagement : {};
  const parts: string[] = [];
  const calls = typeof e.calls === "number" ? e.calls : 0;
  if (calls) parts.push(`${calls} call${calls > 1 ? "s" : ""} (${minutes(e.callSeconds)})`);
  if (typeof e.chatMessages === "number") parts.push(`${e.chatMessages} chat answer${e.chatMessages === 1 ? "" : "s"}`);
  if (typeof record.costUsd === "number") parts.push(`cost $${record.costUsd.toFixed(3)}`);
  return parts.join(" · ");
}
