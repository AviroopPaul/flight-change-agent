import { AnimatePresence, MotionConfig, motion, type Transition } from "motion/react";
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
import { cardMeta } from "../cards/cardMeta";
import { FareTable, InlineCard } from "../cards/InlineCard";
import { RecordCard } from "../record/RecordCard";
import { useHeldCards } from "@/hooks/useHeldCards";

interface Props {
  items: ThreadItem[];
  cards: Record<string, CardEntry>;
  onAnswer: (card: OpenCard, answer: Answer) => void;
  /** The newest final record, until the user closes it. */
  record: FinalRecord | null;
  onCloseRecord: () => void;
  /** A live call is on, so cards wait for the agent to speak. */
  inCall: boolean;
  agentSpeaking: boolean;
}

/**
 * The glass sits on the animated element itself. A parent that fades would cut the card off
 * from the page behind it, and the blur would pop in only after the fade.
 */
const CARD = "glass-card pointer-events-auto shrink-0 origin-[50%_85%]";

/** The card rises out of the dark, a little small, and settles with a soft spring. */
const ENTER = { opacity: 0, y: 44, scale: 0.9 };
const SHOWN = { opacity: 1, y: 0, scale: 1 };
/** An answered card lifts away, so the next one can move up into its place. */
const LEAVE = { opacity: 0, y: -18, scale: 0.94, transition: { duration: 0.22, ease: [0.4, 0, 1, 1] } } as const;
const SPRING: Transition = {
  type: "spring",
  stiffness: 300,
  damping: 26,
  mass: 0.9,
  opacity: { duration: 0.3, ease: "easeOut" },
  layout: { type: "spring", stiffness: 340, damping: 32 },
};

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
export function FloatingCards({ items, cards, onAnswer, record, onCloseRecord, inCall, agentSpeaking }: Props) {
  const ids = useHeldCards(openCardIds(items, cards), items, cards, inCall, agentSpeaking);
  const any = ids.length > 0 || record !== null;
  return (
    <MotionConfig reducedMotion="user">
      {/* Phones have no side room, so the stage dims behind the cards. The call controls stay usable below it. */}
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none fixed inset-x-0 top-0 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-20 bg-black/40 backdrop-blur-[6px] transition-opacity duration-500 sm:hidden",
          any ? "opacity-100" : "opacity-0",
        )}
      />
      <div
        aria-label="Requested inputs"
        className={cn(
          "thin-scroll pointer-events-none fixed z-30 flex flex-col gap-3 overflow-x-hidden overflow-y-auto overscroll-contain p-3",
          "inset-x-1 bottom-[calc(5.75rem+env(safe-area-inset-bottom))] max-h-[62dvh]",
          "sm:inset-x-auto sm:right-3 sm:w-[424px]",
          "lg:top-[4.25rem] lg:bottom-20 lg:max-h-none lg:justify-center-safe xl:bottom-2",
        )}
      >
        <AnimatePresence initial={false} mode="popLayout">
          {ids.map((id) => (
            <motion.div key={id} layout="position" initial={ENTER} animate={SHOWN} exit={LEAVE} transition={SPRING} className={CARD}>
              <InputCard id={id} entry={cards[id]} onAnswer={onAnswer} />
            </motion.div>
          ))}
          {record && (
            <motion.div key="record" layout="position" initial={ENTER} animate={SHOWN} exit={LEAVE} transition={SPRING} className={CARD}>
              <RecordCard record={record} onClose={onCloseRecord} className="my-0 bg-transparent ring-0" />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </MotionConfig>
  );
}

const TITLE = "text-base leading-snug font-medium tracking-tight text-balance";

function InputCard({ id, entry, onAnswer }: { id: string; entry: CardEntry; onAnswer: Props["onAnswer"] }) {
  const card = toOpenCard(id, entry);
  const { spec } = card;
  const typed = usesTextBar(spec);
  const isFare = spec.kind === InputKind.CONFIRM && fareLines(spec.label) !== null;
  const text = spec.label || spec.field || "Input";
  const answer = (value: Answer) => onAnswer(card, value);
  const { icon: Icon, eyebrow } = cardMeta(spec);

  return (
    <section aria-labelledby={labelId(spec)} className="stagger p-[1.125rem]">
      <header className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-glow/12 text-glow-2 shadow-[inset_0_0_0_1px_color-mix(in_oklch,var(--glow)_35%,transparent),inset_0_1px_0_0_oklch(1_0_0/0.25),0_6px_18px_-8px_var(--primary)]">
          <Icon className="size-[17px]" strokeWidth={2.1} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium tracking-[0.08em] text-glow uppercase">{eyebrow}</p>
          {isFare ? (
            <p className={TITLE}>Review the new price</p>
          ) : isChoiceKind(spec.kind) || !typed ? (
            <h3 className={TITLE} id={labelId(spec)}>{text}</h3>
          ) : (
            <label className={cn("block", TITLE)} id={labelId(spec)} htmlFor={inputId(spec)}>{text}</label>
          )}
          {spec.help && <p className="mt-0.5 text-[13px] text-muted-foreground">{spec.help}</p>}
        </div>
      </header>
      {isFare && (
        <div id={labelId(spec)} className="mt-3">
          <FareTable label={spec.label} />
        </div>
      )}
      {typed ? (
        <div className="mt-4">
          <TypedAnswer key={card.key} card={card} onAnswer={answer} />
        </div>
      ) : (
        <InlineCard key={card.key} card={card} onAnswer={answer} />
      )}
    </section>
  );
}
