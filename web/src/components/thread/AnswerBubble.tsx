import type { InputRequest } from "../../protocol";
import type { Answer } from "../../state/conversation";
import { FileRow } from "./FileRow";
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
    <div className={`bubble user${acked ? " acked" : ""}`}>
      {caption && <span className="caption">{spec.label || spec.field}</span>}
      {files.length ? files.map((file, i) => <FileRow key={`${i}:${file.name}`} file={file} />) : answer.display}
      <Stamp time={time} ticks={acked ? "sent" : "sending"} />
    </div>
  );
}
