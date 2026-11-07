interface Props {
  disabled: boolean;
  onStop: () => void;
}

/** Asks the backend to stop the request. The backend shows a confirm card first. */
export function StopButton({ disabled, onStop }: Props) {
  return (
    <button className="stop-btn" type="button" disabled={disabled} onClick={onStop} title="Stop this request">
      Stop request
    </button>
  );
}
