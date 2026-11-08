import { ArrowUp } from "lucide-react";

export function SendButton({ disabled = false }: { disabled?: boolean }) {
  return (
    <button
      type="submit"
      aria-label="Send"
      disabled={disabled}
      className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground transition-all outline-none hover:brightness-110 focus-visible:ring-2 focus-visible:ring-ring disabled:bg-white/10 disabled:text-muted-foreground disabled:shadow-none"
    >
      <ArrowUp className="size-5" />
    </button>
  );
}
