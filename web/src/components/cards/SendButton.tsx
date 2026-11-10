import { ArrowUp } from "lucide-react";

export function SendButton({ disabled = false }: { disabled?: boolean }) {
  return (
    <button
      type="submit"
      aria-label="Send"
      disabled={disabled}
      className="btn-glow grid size-10 shrink-0 place-items-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:bg-none disabled:bg-white/10 disabled:text-muted-foreground disabled:shadow-none disabled:filter-none"
    >
      <ArrowUp className="size-5" strokeWidth={2.5} />
    </button>
  );
}
