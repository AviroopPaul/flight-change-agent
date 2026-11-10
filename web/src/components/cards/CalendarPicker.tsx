import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

const WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

const pad = (n: number) => String(n).padStart(2, "0");
const iso = (y: number, m: number, d: number) => `${y}-${pad(m + 1)}-${pad(d)}`;

/** Days of one month as a Monday-first grid; null fills the cells before the 1st. */
function monthCells(year: number, month: number): (number | null)[] {
  const lead = (new Date(year, month, 1).getDay() + 6) % 7;
  const days = new Date(year, month + 1, 0).getDate();
  return [...Array<null>(lead).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)];
}

interface Props {
  /** The selected day as YYYY-MM-DD, or "". */
  value: string;
  /** The first day that can be picked, YYYY-MM-DD. There is no last day. */
  min: string;
  onChange: (value: string) => void;
}

/** A month calendar that is always visible inside the card. Past days are disabled; any later month is open. */
export function CalendarPicker({ value, min, onChange }: Props) {
  const start = value || min;
  const [view, setView] = useState(() => ({ y: Number(start.slice(0, 4)), m: Number(start.slice(5, 7)) - 1 }));
  const minMonth = min.slice(0, 7);
  const atFirstMonth = iso(view.y, view.m, 1).slice(0, 7) <= minMonth;
  const shift = (by: number) =>
    setView(({ y, m }) => {
      const next = new Date(y, m + by, 1);
      return { y: next.getFullYear(), m: next.getMonth() };
    });
  const title = new Date(view.y, view.m, 1).toLocaleDateString("en-GB", { month: "long", year: "numeric" });

  return (
    <div className="well rounded-[1.15rem] p-2.5">
      <div className="mb-1.5 flex items-center justify-between">
        <button
          type="button"
          onClick={() => shift(-1)}
          disabled={atFirstMonth}
          aria-label="Previous month"
          className="grid size-8 place-items-center rounded-lg text-muted-foreground outline-none hover:bg-white/[0.06] hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-30"
        >
          <ChevronLeft className="size-4" />
        </button>
        <p className="text-sm font-medium" aria-live="polite">{title}</p>
        <button
          type="button"
          onClick={() => shift(1)}
          aria-label="Next month"
          className="grid size-8 place-items-center rounded-lg text-muted-foreground outline-none hover:bg-white/[0.06] hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronRight className="size-4" />
        </button>
      </div>
      <div role="grid" aria-label={title} className="grid grid-cols-7 gap-0.5 text-center">
        {WEEKDAYS.map((d) => (
          <span key={d} className="py-1 text-[11px] text-muted-foreground">{d}</span>
        ))}
        {monthCells(view.y, view.m).map((day, i) => {
          if (day === null) return <span key={`blank-${i}`} />;
          const date = iso(view.y, view.m, day);
          const past = date < min;
          const selected = date === value;
          return (
            <button
              key={date}
              type="button"
              disabled={past}
              aria-pressed={selected}
              aria-label={new Date(view.y, view.m, day).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
              onClick={() => onChange(date)}
              className={cn(
                "h-9 rounded-lg text-[13px] tabular-nums outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                past ? "text-muted-foreground/35" : "hover:bg-white/[0.08]",
                date === min && !selected && "ring-1 ring-white/25",
                selected && "bg-primary font-semibold text-primary-foreground hover:bg-primary",
              )}
            >
              {day}
            </button>
          );
        })}
      </div>
    </div>
  );
}
