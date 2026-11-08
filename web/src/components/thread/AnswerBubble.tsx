import type { InputRequest } from "../../protocol";
import type { Answer } from "../../state/conversation";
import { FileRow } from "./FileRow";
import { UserBubble } from "./Message";
import { Stamp } from "./Stamp";

interface Props {
  spec: InputRequest;
  answer: Answer;
  acked: boolean;
  time: string;
  /** False when the question sits right above, so the caption would only repeat it. */
  caption?: boolean;
}

export function AnswerBubble({ spec, answer, acked, time, caption = true }: Props) {
  const files = answer.files ?? [];
  return (
    <UserBubble>
      {caption && (
        <span className="mb-0.5 block font-mono text-[10px] tracking-[0.14em] text-glow/80 uppercase">{spec.label || spec.field}</span>
      )}
      <div className="text-[15px] leading-relaxed whitespace-pre-wrap">
        {files.length ? files.map((file, i) => <FileRow key={`${i}:${file.name}`} file={file} />) : answer.display}
      </div>
      <Stamp time={time} ticks={acked ? "sent" : "sending"} className="justify-end" />
    </UserBubble>
  );
}
