import { Check, ChevronUp, Mic, MicOff } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { MicDevices } from "@/hooks/useMicDevices";
import { cn } from "@/lib/utils";

interface Props {
  inCall: boolean;
  muted: boolean;
  /** Mic loudness, 0 to 1. */
  level: number;
  mics: MicDevices;
  onMute: (muted: boolean) => void;
  onPick: (deviceId: string) => void;
}

const DEFAULT_ID = "default";

/** A split button: the left half mutes, the chevron opens the microphone list. */
export function MicControl({ inCall, muted, level, mics, onMute, onPick }: Props) {
  const live = inCall && !muted;
  const glow = live ? Math.min(1, level * 2.5) : 0;
  const label = !inCall ? "Mic turns on with the call" : muted ? "Unmute" : "Mute";
  const current = mics.devices.find((d) => d.deviceId === mics.deviceId);

  return (
    <div className="flex items-center rounded-full bg-white/[0.06] ring-1 ring-white/10">
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={muted ? "Unmute microphone" : "Mute microphone"}
            aria-pressed={muted}
            disabled={!inCall}
            onClick={() => onMute(!muted)}
            className={cn(
              "relative grid size-12 place-items-center rounded-full transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring",
              muted ? "bg-destructive/20 text-destructive" : "text-foreground hover:bg-white/10",
              "disabled:cursor-not-allowed disabled:text-muted-foreground",
            )}
          >
            {/* The ring breathes with the caller's voice, so they can see the mic is picking them up. */}
            <span
              className="pointer-events-none absolute inset-1 rounded-full transition-[box-shadow] duration-75"
              style={{ boxShadow: `0 0 0 ${1 + glow * 5}px color-mix(in oklch, var(--glow) ${Math.round(15 + glow * 55)}%, transparent)` }}
            />
            {muted ? <MicOff className="size-5" /> : <Mic className="size-5" />}
          </button>
        </TooltipTrigger>
        <TooltipContent>{label}</TooltipContent>
      </Tooltip>

      <DropdownMenu onOpenChange={(open) => open && !mics.labelled && void mics.unlock()}>
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="Choose microphone"
                className="grid h-12 w-8 place-items-center rounded-full pr-1 text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
              >
                <ChevronUp className="size-4" />
              </button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent>{current?.label || "Microphone"}</TooltipContent>
        </Tooltip>
        <DropdownMenuContent side="top" align="start" sideOffset={10} className="w-72 max-w-[calc(100vw-2rem)]">
          <DropdownMenuLabel className="text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground">
            Microphone
          </DropdownMenuLabel>
          <DropdownMenuRadioGroup value={mics.deviceId || DEFAULT_ID} onValueChange={(id) => onPick(id === DEFAULT_ID ? "" : id)}>
            {!mics.devices.some((d) => d.deviceId === DEFAULT_ID) && (
              <DropdownMenuRadioItem value={DEFAULT_ID}>System default</DropdownMenuRadioItem>
            )}
            {mics.devices.map((d, i) => (
              <DropdownMenuRadioItem key={d.deviceId || i} value={d.deviceId || DEFAULT_ID}>
                <span className="truncate">{d.label || `Microphone ${i + 1}`}</span>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
          {!mics.labelled && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={(e) => { e.preventDefault(); void mics.unlock(); }}>
                <Check className="size-4" /> Allow mic access to see names
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
