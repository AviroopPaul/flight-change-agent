import { CalendarDays, CircleHelp, Hash, Keyboard, ListChecks, Mail, Paperclip, Phone, Plane, ReceiptText, type LucideIcon } from "lucide-react";
import { fareLines, optionParts } from "@/lib/cardView";
import { InputKind, type InputRequest } from "@/protocol";

export interface CardMeta {
  icon: LucideIcon;
  /** The small line over the question: what kind of answer the card wants. */
  eyebrow: string;
}

const BY_KIND: Record<InputKind, CardMeta> = {
  [InputKind.TEXT]: { icon: Keyboard, eyebrow: "Type it in" },
  [InputKind.EMAIL]: { icon: Mail, eyebrow: "Email" },
  [InputKind.PHONE]: { icon: Phone, eyebrow: "Phone number" },
  [InputKind.NUMBER]: { icon: Hash, eyebrow: "Number" },
  [InputKind.DATE]: { icon: CalendarDays, eyebrow: "Pick a date" },
  [InputKind.SELECT]: { icon: ListChecks, eyebrow: "Choose one" },
  [InputKind.MULTI_SELECT]: { icon: ListChecks, eyebrow: "Choose any" },
  [InputKind.FILE]: { icon: Paperclip, eyebrow: "Attach" },
  [InputKind.CONFIRM]: { icon: CircleHelp, eyebrow: "Confirm" },
};

/** The icon and eyebrow for a card. Flight lists and the fare card get their own. */
export function cardMeta(spec: InputRequest): CardMeta {
  if (spec.kind === InputKind.CONFIRM && fareLines(spec.label)) return { icon: ReceiptText, eyebrow: "Fare change" };
  if (spec.kind === InputKind.SELECT && spec.options?.some((option) => optionParts(option.label ?? ""))) {
    return { icon: Plane, eyebrow: "Choose a flight" };
  }
  return BY_KIND[spec.kind] ?? BY_KIND[InputKind.TEXT];
}
