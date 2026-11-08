import { useState } from "react";
import * as config from "./config";
import { Header } from "./components/header/Header";
import { Thread } from "./components/thread/Thread";
import { createDemo } from "./demo/demo";
import { useCall } from "./hooks/useCall";
import { useChat } from "./hooks/useChat";
import { useSession } from "./hooks/useSession";
import { useConversation } from "./hooks/useConversation";
import { initialState, isInCall, ThreadItemKind } from "./state/conversation";

export function App() {
  const { state, barCard, ui, submit } = useConversation(() =>
    config.setupProblem ? initialState({ text: "no server configured", disabled: true }, config.setupProblem) : initialState(),
  );
  const session = useSession(config.backend);
  const call = useCall(ui, config.backend, session.sessionId);
  const chat = useChat(ui, config.backend, session.sessionId);
  const notice = state.notice ?? session.error;
  const submitted = state.items.some((item) => item.kind === ThreadItemKind.RECORD);
  const [demo] = useState(() => (config.demo ? createDemo(ui, config.demoPace) : null));

  const controls = demo ?? call;
  const sendInput = demo?.sendInput ?? chat.sendInput;
  const onCall = () => (isInCall(state.call.state) ? controls.hangUp() : controls.start());

  return (
    <>
      <Header
        call={state.call}
        notice={notice}
        onCall={onCall}
        onStop={chat.optOut}
        stopDisabled={!session.sessionId || submitted || Boolean(demo)}
      />
      <Thread
        serverLabel={config.serverLabel}
        sessionId={session.sessionId ?? "starting…"}
        items={state.items}
        cards={state.cards}
        barCard={barCard}
        onAnswer={(open, answer) => submit(open.spec, answer, sendInput)}
      />
    </>
  );
}
