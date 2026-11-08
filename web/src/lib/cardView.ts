/** Helpers that turn the server's card text into a richer layout. Pure, and safe on any text. */

export interface OptionParts {
  title: string;
  subtitle: string;
  price: string;
  note: string;
}

/** "AQ104 · 12 Nov 17:45 → 20:30 · ₹6,700/person · you pay ₹4,300" -> parts for a flight row. */
export function optionParts(label: string): OptionParts | null {
  const parts = label.split(" · ");
  if (parts.length < 4) return null;
  const [code, when, price, ...rest] = parts;
  const m = /^(.*?)\s+(\d{1,2}:\d{2}\s*→\s*\d{1,2}:\d{2})$/.exec(when);
  return {
    title: m ? m[2] : when,
    subtitle: m ? `${code} · ${m[1]}` : code,
    price,
    note: rest.join(" · "),
  };
}

export interface FareLine {
  label: string;
  amount: string;
  total: boolean;
}

/** "Old fare ₹5,400/person. New fare ₹6,700/person. ... You pay ₹4,300. Accept this change?" */
export function fareLines(label: string): { lines: FareLine[]; other: string[]; question: string } | null {
  const sentences = label.split(/(?<=[.?])\s+/).map((s) => s.trim()).filter(Boolean);
  const question = sentences.at(-1)?.endsWith("?") ? (sentences.pop() as string) : "";
  const lines: FareLine[] = [];
  const other: string[] = [];
  for (const raw of sentences) {
    const s = raw.replace(/\.$/, "");
    const m = /^(.*?)\s+(₹[\d,]+(?:\/person)?)(.*)$/.exec(s);
    if (m) lines.push({ label: m[1], amount: m[2] + m[3], total: /^(you pay|refund)/i.test(m[1]) });
    else other.push(s);
  }
  return lines.length >= 2 ? { lines, other, question } : null;
}
