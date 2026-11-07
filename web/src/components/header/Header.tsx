import { isInCall, type CallStatus } from "../../state/conversation";
import { AvatarIcon, PhoneIcon } from "../icons";
import { CallTimer } from "./CallTimer";
import { MicMeter } from "./MicMeter";
import { StopButton } from "./StopButton";
import { Banner } from "../thread/Banner";

interface Props {
  call: CallStatus;
  notice: string | null;
  onCall: () => void;
  onStop: () => void;
  stopDisabled: boolean;
}

export function Header({ call, notice, onCall, onStop, stopDisabled }: Props) {
  const inCall = isInCall(call.state);
  return (
    <>
      <header className="topbar">
        <div className="avatar" aria-hidden="true"><AvatarIcon /></div>
        <div className="titles">
          <h1>Flight change</h1>
          <span className="status" data-state={call.state}>
            <span className="status-text" role="status" title={call.text}>{call.text}</span>
            {call.connectedAt !== null && <CallTimer since={call.connectedAt} />}
          </span>
        </div>
        <button
          className={`call-btn${inCall ? " hangup" : ""}`}
          type="button"
          aria-label={inCall ? "Hang up" : "Start call"}
          title="Use headphones; browser echo cancellation is best-effort."
          disabled={call.disabled}
          onClick={onCall}
        >
          <PhoneIcon />
        </button>
        <MicMeter />
        <StopButton disabled={stopDisabled} onStop={onStop} />
      </header>
      <Banner call={call} />
      {notice && <p className="notice" role="status">{notice}</p>}
    </>
  );
}
