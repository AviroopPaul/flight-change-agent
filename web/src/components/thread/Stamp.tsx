import { Check, CheckCheck, Mic } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  time: string;
  spoken?: boolean;
  ticks?: "sending" | "sent";
  className?: string;
}

/** The small line under an entry: spoken or typed, the time, and whether the server has the answer. */
export function Stamp({ time, spoken = false, ticks, className }: Props) {
  return (
    <span className={cn("mt-1 flex items-center gap-1 text-[10.5px] text-muted-foreground/75 tabular-nums", className)}>
      {spoken && <Mic className="size-3" aria-label="spoken" />}
      {time}
      {ticks === "sending" && <Check className="size-3" aria-label="sending" />}
      {ticks === "sent" && <CheckCheck className="size-3.5 text-glow" aria-label="sent" />}
    </span>
  );
}
