import { Phone } from "lucide-react";

/** At the end of the thread once a call has ended: continue by voice, with full context. */
export function CallBackPrompt({ onCall }: { onCall: () => void }) {
  return (
    <div className="flex items-center gap-3 self-start rounded-2xl bg-white/[0.04] px-3 py-2.5 ring-1 ring-white/[0.08]">
      <p className="text-sm text-muted-foreground">The call ended. Want to continue by voice?</p>
      <button
        type="button"
        onClick={onCall}
        className="flex h-8 shrink-0 items-center gap-1.5 rounded-full bg-primary px-3 text-sm font-medium text-primary-foreground transition-all outline-none hover:brightness-110 focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Phone className="size-3.5" /> Call me back
      </button>
    </div>
  );
}
