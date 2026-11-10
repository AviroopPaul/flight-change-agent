import { PhoneCall } from "lucide-react";

/** At the end of the thread once a call has ended: continue by voice, with full context. */
export function CallBackPrompt({ onCall }: { onCall: () => void }) {
  return (
    <div className="flex items-center gap-3 self-start well rounded-[1.4rem] py-2 pr-2 pl-4">
      <p className="text-sm text-muted-foreground">The call ended. Want to continue by voice?</p>
      <button
        type="button"
        onClick={onCall}
        className="btn-glow flex h-9 shrink-0 items-center gap-1.5 rounded-full px-3.5 text-sm font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <PhoneCall className="size-3.5" strokeWidth={2.4} /> Call me back
      </button>
    </div>
  );
}
