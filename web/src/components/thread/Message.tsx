import type { ReactNode } from "react";
import { Role } from "../../protocol";
import { cn } from "@/lib/utils";
import { Stamp } from "./Stamp";

interface Props {
  role: Role;
  text: string;
  time: string;
  /** From the call transcript rather than typed. */
  spoken?: boolean;
  /** Still being recognized. */
  partial?: boolean;
  grouped?: boolean;
}

export function Message({ role, text, time, spoken = false, partial = false, grouped = false }: Props) {
  if (role === Role.AGENT) {
    return (
      <AgentRow grouped={grouped}>
        <p className={cn("text-[15px] leading-relaxed whitespace-pre-wrap", partial ? "shimmer" : "text-foreground/95")}>{text}</p>
        <Stamp time={time} spoken={spoken} />
      </AgentRow>
    );
  }
  return (
    <UserBubble>
      <p className={cn("text-[15px] leading-relaxed whitespace-pre-wrap", partial && "shimmer")}>{text}</p>
      <Stamp time={time} spoken={spoken} className="justify-end" />
    </UserBubble>
  );
}

/** The agent's side: no bubble, just a small orb avatar and the words, the way an assistant answers. */
export function AgentRow({ grouped = false, wide = false, children }: { grouped?: boolean; wide?: boolean; children: ReactNode }) {
  return (
    <div className={cn("flex max-w-[94%] gap-3 self-start", wide && "w-full", grouped && "-mt-1")}>
      <span className={cn("agent-dot mt-1 size-5 shrink-0 rounded-full", grouped && "invisible")} aria-hidden="true" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export function UserBubble({ children }: { children: ReactNode }) {
  return (
    <div className="max-w-[85%] self-end overflow-hidden well rounded-[1.4rem] rounded-br-lg px-4 py-2 [overflow-wrap:anywhere]">
      {children}
    </div>
  );
}
