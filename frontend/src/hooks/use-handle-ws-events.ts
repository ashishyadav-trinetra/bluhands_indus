import React from "react";
import { AgentState } from "#/types/agent-state";
import ActionType from "#/types/action-type";
import { displayErrorToast } from "#/utils/custom-toast-handlers";
import { useEventStore } from "#/stores/use-event-store";
import { useSendMessage } from "#/hooks/use-send-message";

interface ServerError {
  error: boolean | string;
  message: string;
  [key: string]: unknown;
}

const isServerError = (data: object): data is ServerError => "error" in data;

export const useHandleWSEvents = () => {
  const { send } = useSendMessage();
  const events = useEventStore((state) => state.events);

  React.useEffect(() => {
    if (!events.length) {
      return;
    }
    const event = events[events.length - 1];

    if (isServerError(event)) {
      if (event.error_code === 401) {
        displayErrorToast("Session expired.");
        return;
      }

      if (typeof event.error === "string") {
        displayErrorToast(event.error);
      } else {
        displayErrorToast(event.message);
      }
      return;
    }

    if ("type" in event && event.type === "error") {
      const message: string = `${event.message}`;
      if (message.startsWith("Agent reached maximum")) {
        // We set the agent state to paused here - if the user clicks resume, it auto updates the max iterations
        send({ action: ActionType.CHANGE_AGENT_STATE, args: { agent_state: AgentState.PAUSED } });
      }
    }
  }, [events.length]);
};
