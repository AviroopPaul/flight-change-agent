import { ArrowDown, CircleCheck, CircleSlash, Sparkles } from "lucide-react";
import { fareLines } from "../../lib/cardView";
import { inputId, isChoiceKind, labelId } from "../../lib/inputs";
import { InputKind } from "../../protocol";
import { CardStatus, toOpenCard, usesTextBar, type Answer, type CardEntry, type OpenCard } from "../../state/conversation";
import { FareTable, InlineCard } from "../cards/InlineCard";
import { cn } from "@/lib/utils";
import { AgentRow } from "./Message";

interface Props {
  id: string;
  entry: CardEntry;
  onAnswer: (card: OpenCard, answer: Answer) => void;
  grouped?: boolean;
  interactive: boolean;
}

const STATUS_LINE: Record<CardStatus, { text: string; icon: typeof Sparkles }> = {
  [CardStatus.OPEN]: { text: "Input requested", icon: Sparkles },
  [CardStatus.QUEUED]: { text: "Up next", icon: Sparkles },
  [CardStatus.SUBMITTED]: { text: "Answered", icon: CircleCheck },
  [CardStatus.CANCELLED]: { text: "No longer needed", icon: CircleSlash },
};

/** A question from the agent, in the thread. Its answer controls sit inside it, except typed answers (text bar). */
export function Prompt({ id, entry, onAnswer, grouped, interactive }: Props) {
  const { spec, status } = entry;
  const open = status === CardStatus.OPEN;
  const inline = interactive && open && !usesTextBar(spec);
  const isFare = spec.kind === InputKind.CONFIRM && fareLines(spec.label) !== null;
  const text = spec.label || spec.field || "Input";
  const card = toOpenCard(id, entry);
  const labelled = isChoiceKind(spec.kind) || !inline;
  const line = STATUS_LINE[status];
  const LineIcon = line.icon;

  return (
    <AgentRow grouped={grouped} wide>
      <div
        className={cn(
          "w-full max-w-md rounded-[1.5rem] p-4 transition-all duration-300",
          open
            ? "bg-white/[0.05] shadow-[inset_0_0_0_1px_oklch(1_0_0/0.14),inset_0_1px_0_0_oklch(1_0_0/0.16)]"
            : "bg-white/[0.02] ring-1 ring-white/[0.07]",
          status === CardStatus.CANCELLED && "opacity-55",
        )}
      >
        <span
          className={cn(
            "mb-2 flex items-center gap-1.5 font-mono text-[10px] tracking-[0.16em] uppercase",
            open ? "text-glow" : "text-muted-foreground",
          )}
        >
          <LineIcon className="size-3" /> {line.text}
        </span>
        {isFare ? (
          <div id={interactive ? labelId(spec) : undefined}><FareTable label={spec.label} /></div>
        ) : labelled ? (
          <span className="block text-[15px] leading-snug font-medium" id={interactive ? labelId(spec) : undefined}>{text}</span>
        ) : (
          <label className="block text-[15px] leading-snug font-medium" id={interactive ? labelId(spec) : undefined} htmlFor={inputId(spec)}>{text}</label>
        )}
        {spec.help && <p className="mt-1 text-[13px] text-muted-foreground">{spec.help}</p>}
        {interactive && open && usesTextBar(spec) && (
          <p className="mt-3 flex items-center gap-1.5 text-[12.5px] text-muted-foreground">
            <ArrowDown className="size-3.5" /> Type your answer in the box below.
          </p>
        )}
        {inline && <InlineCard key={card.key} card={card} onAnswer={(answer) => onAnswer(card, answer)} />}
      </div>
    </AgentRow>
  );
}
