import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Keyboard, Paperclip } from "lucide-react";
import { useFocusOnOpen } from "../../hooks/useFocusOnOpen";
import { fileAnswer, textAnswer } from "../../lib/answers";
import { prefillFileInput } from "../../lib/files";
import { INPUT_TYPES, inputId } from "../../lib/inputs";
import { InputKind } from "../../protocol";
import type { Answer, OpenCard } from "../../state/conversation";
import { cn } from "@/lib/utils";
import { ErrorLine } from "./ErrorLine";
import { SendButton } from "./SendButton";

interface Props {
  card: OpenCard | null;
  onAnswer: (answer: Answer) => void;
}

const MAX_ROWS_PX = 140;

const shell = "rounded-2xl bg-white/[0.04] p-1.5 pl-4 ring-1 ring-white/10 transition-shadow";

/** The bottom bar. It answers the open typed question, and waits when there is none. */
export function Composer({ card, onAnswer }: Props) {
  return (
    <div className="shrink-0 border-t border-white/[0.07] px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      <div className="mx-auto max-w-2xl">
        {card ? <ActiveComposer key={card.key} card={card} onAnswer={onAnswer} /> : <IdleComposer />}
      </div>
    </div>
  );
}

function IdleComposer() {
  return (
    <div className={cn(shell, "flex items-center gap-2 opacity-70")}>
      <Keyboard className="size-4 shrink-0 text-muted-foreground" />
      <input
        disabled
        aria-label="Message"
        placeholder="Answer the cards above, or just talk on the call"
        className="h-10 min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted-foreground"
      />
      <SendButton disabled />
    </div>
  );
}

function ActiveComposer({ card, onAnswer }: { card: OpenCard; onAnswer: (answer: Answer) => void }) {
  const { spec, previous } = card;
  const [error, setError] = useState(card.error);
  const [text, setText] = useState(previous?.value != null ? String(previous.value) : "");
  const [files, setFiles] = useState<File[]>(previous?.files ?? []);
  const formRef = useRef<HTMLFormElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const isFile = spec.kind === InputKind.FILE;
  // Free text gets a growing text area; emails, phones and numbers keep a typed input for the right keyboard.
  const isArea = spec.kind === InputKind.TEXT;

  useEffect(() => {
    if (isFile && inputRef.current) prefillFileInput(inputRef.current, files);
  }, []);
  useFocusOnOpen(formRef);
  useLayoutEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_ROWS_PX)}px`;
  }, [text]);

  const submit = () => {
    const result = isFile ? fileAnswer(spec, files) : textAnswer(spec, text, isArea ? null : inputRef.current);
    if (typeof result === "string") setError(result);
    else onAnswer(result);
  };
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit();
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  const names = files.map((file) => file.name).join(", ");
  const placeholder = spec.placeholder || spec.label || "Type here";
  return (
    <form ref={formRef} noValidate onSubmit={onSubmit} onChange={() => setError(null)}>
      <ErrorLine message={error} className="mt-0 mb-2 px-1" />
      <div
        className={cn(
          shell,
          "flex items-end gap-2 focus-within:ring-white/25",
          error && "ring-destructive/50",
        )}
      >
        {isFile ? (
          <label className="flex h-10 min-w-0 flex-1 cursor-pointer items-center gap-2 text-[15px] text-muted-foreground focus-within:text-foreground">
            <input
              ref={inputRef}
              type="file"
              id={inputId(spec)}
              className="sr-only"
              multiple={Boolean(spec.multiple)}
              accept={spec.accept}
              onChange={(event) => setFiles([...(event.target.files ?? [])])}
            />
            <Paperclip className="size-4 shrink-0" />
            <span className="truncate">{names || (spec.multiple ? "Attach files" : "Attach a file")}</span>
          </label>
        ) : isArea ? (
          <textarea
            ref={areaRef}
            id={inputId(spec)}
            rows={1}
            placeholder={placeholder}
            value={text}
            onKeyDown={onKeyDown}
            onChange={(event) => setText(event.target.value)}
            className="thin-scroll max-h-36 min-w-0 flex-1 resize-none bg-transparent py-2 text-[15px] leading-6 outline-none placeholder:text-muted-foreground"
          />
        ) : (
          <input
            ref={inputRef}
            type={INPUT_TYPES[spec.kind] ?? "text"}
            id={inputId(spec)}
            placeholder={placeholder}
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="h-10 min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted-foreground"
          />
        )}
        <SendButton />
      </div>
      <p className="mt-1.5 px-1 text-[11px] text-muted-foreground/70">
        {isArea ? "Enter to send · Shift + Enter for a new line" : "The agent hears about it as soon as you send."}
      </p>
    </form>
  );
}
