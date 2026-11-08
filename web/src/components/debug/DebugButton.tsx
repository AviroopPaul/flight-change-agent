import { Activity } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { TOP_BUTTON } from "../stage/topButton";

export function DebugButton({ open, disabled, onToggle }: { open: boolean; disabled: boolean; onToggle: () => void }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" onClick={onToggle} disabled={disabled} aria-expanded={open} aria-label="Debug view" className={TOP_BUTTON}>
          <Activity className="size-4" />
          <span className="hidden sm:inline">Debug</span>
        </button>
      </TooltipTrigger>
      <TooltipContent>Session timeline: both channels, agent tools, latency and cost</TooltipContent>
    </Tooltip>
  );
}
