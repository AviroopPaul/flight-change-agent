import { ClipboardList } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { TOP_BUTTON } from "../stage/topButton";

export function GuideButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" onClick={onToggle} aria-expanded={open} aria-label="Demo guide" className={TOP_BUTTON}>
          <ClipboardList className="size-4" />
          <span className="hidden sm:inline">Guide</span>
        </button>
      </TooltipTrigger>
      <TooltipContent>Test bookings and demo scenarios</TooltipContent>
    </Tooltip>
  );
}
