import { CircleAlert } from "lucide-react";
import { cn } from "@/lib/utils";

export function ErrorLine({ message, className }: { message: string | null; className?: string }) {
  return (
    <p
      role="alert"
      hidden={!message}
      className={cn("mt-2 flex items-start gap-1.5 text-[13px] leading-snug text-destructive [&[hidden]]:hidden", className)}
    >
      <CircleAlert className="mt-px size-3.5 shrink-0" />
      {message}
    </p>
  );
}
