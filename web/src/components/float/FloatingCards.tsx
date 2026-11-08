import { AnimatePresence, motion } from "motion/react";
import { Sparkles } from "lucide-react";
import { fareLines } from "@/lib/cardView";
import { inputId, isChoiceKind, labelId } from "@/lib/inputs";
import { cn } from "@/lib/utils";
import { InputKind, type FinalRecord } from "@/protocol";
import {
  CardStatus,
  ThreadItemKind,
  toOpenCard,
  usesTextBar,
  type Answer,
  type CardEntry,
  type OpenCard,
  type ThreadItem,
} from "@/state/conversation";
import { TypedAnswer } from "../cards/Composer";
import { FareTable, InlineCard } from "../cards/InlineCard";
import { RecordCard } from "../record/RecordCard";

interface Props {
  items: ThreadItem[];
  cards: Record<string, CardEntry>;
  onAnswer: (card: OpenCard, answer: Answer) => void;
  /** The newest final record, until the user closes it. */
  record: FinalRecord | null;
  onCloseRecord: () => void;
}

/** A solid panel, so the cards stay readable over the orb. */
const PANEL = "rounded-2xl bg-[oklch(0.18_0.024_264/0.94)] ring-1 ring-white/10 shadow-[0_24px_64px_-24px_rgb(0_0_0/0.85)] backdrop-blur-xl";

const ENTER = { opacity: 0, x: 32 };
const SHOWN = { opacity: 1, x: 0, scale: 1 };
const LEAVE = { opacity: 0, x: 32, scale: 0.97 };

/** The cards the agent is waiting on, in the order it asked for them. */
function openCardIds(items: ThreadItem[], cards: Record<string, CardEntry>): string[] {
  const ids = new Set<string>();
  for (const item of items) {
    if (item.kind === ThreadItemKind.PROMPT && cards[item.id]?.status === CardStatus.OPEN) ids.add(item.id);
  }
  return [...ids];
}

/**
 * Voice-first input: each card the agent opens floats at the side (above the controls on phones),
 * and leaves once answered. A rejected answer reopens the card with its error.
 */
export function FloatingCards({ items, cards, onAnswer, record, onCloseRecord }: Props) {
  const ids = openCardIds(items, cards);
  const any = ids.length > 0 || record !== null;
  return (
    <>
      {/* Phones have no side room, so the stage dims behind the cards. The call controls stay usable below it. */}
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none fixed inset-x-0 top-0 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-20 bg-background/70 backdrop-blur-sm transition-opacity duration-300 sm:hidden",
          any ? "opacity-100" : "opacity-0",
        )}
      />
    <div
      aria-label="Requested inputs"
      className={cn(
        "thin-scroll pointer-events-none fixed z-30 flex flex-col gap-3 overflow-y-auto overscroll-contain p-1",
        "inset-x-3 bottom-[calc(6.25rem+env(safe-area-inset-bottom))] max-h-[60dvh]",
        "sm:inset-x-auto sm:right-5 sm:w-[400px]",
        "lg:top-20 lg:bottom-24 lg:max-h-none lg:justify-center",
      )}
    >
      <AnimatePresence initial={false} mode="popLayout">
        {ids.map((id) => (
          <motion.div
            key={id}
            layout
            initial={ENTER}
            animate={SHOWN}
            exit={LEAVE}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="pointer-events-auto shrink-0"
          >
            <InputCard id={id} entry={cards[id]} onAnswer={onAnswer} />
          </motion.div>
        ))}
        {record && (
          <motion.div
            key="record"
            layout
            initial={ENTER}
            animate={SHOWN}
            exit={LEAVE}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="pointer-events-auto shrink-0"
          >
            <RecordCard record={record} onClose={onCloseRecord} className={cn(PANEL, "my-0")} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
    </>
  );
}

function InputCard({ id, entry, onAnswer }: { id: string; entry: CardEntry; onAnswer: Props["onAnswer"] }) {
  const card = toOpenCard(id, entry);
  const { spec } = card;
  const typed = usesTextBar(spec);
  const isFare = spec.kind === InputKind.CONFIRM && fareLines(spec.label) !== null;
  const text = spec.label || spec.field || "Input";
  const answer = (value: Answer) => onAnswer(card, value);

  return (
    <section aria-labelledby={labelId(spec)} className={cn(PANEL, "p-4")}>
      <span className="mb-2 flex items-center gap-2 font-mono text-[10px] tracking-[0.16em] text-glow uppercase">
        <Sparkles className="size-3" /> The agent needs
      </span>
      {isFare ? (
        <div id={labelId(spec)}><FareTable label={spec.label} /></div>
      ) : isChoiceKind(spec.kind) || !typed ? (
        <h3 className="text-[15px] leading-snug font-medium" id={labelId(spec)}>{text}</h3>
      ) : (
        <label className="block text-[15px] leading-snug font-medium" id={labelId(spec)} htmlFor={inputId(spec)}>{text}</label>
      )}
      {spec.help && <p className="mt-1 text-[13px] text-muted-foreground">{spec.help}</p>}
      {typed ? (
        <div className="mt-3">
          <TypedAnswer key={card.key} card={card} onAnswer={answer} />
        </div>
      ) : (
        <InlineCard key={card.key} card={card} onAnswer={answer} />
      )}
    </section>
  );
}
