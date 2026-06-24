import { useEffect, useRef } from "react";
import { useEventStore } from "#/stores/use-event-store";
import { useConversationStore } from "#/stores/conversation-store";
import { useUnifiedActiveHost } from "#/hooks/query/use-unified-active-host";

/**
 * File extension patterns that likely affect a running web app preview.
 * When the agent writes/edits files matching these, we auto-refresh the preview.
 */
const WEB_FILE_PATTERNS =
  /\.(tsx?|jsx?|css|scss|less|html|json|vue|svelte|astro|md|mdx)$/i;

/**
 * Watches for file-write events from the agent and triggers a preview
 * refresh with a short debounce. Only triggers when a served app is active.
 */
export function usePreviewHotReload() {
  const { activeHost } = useUnifiedActiveHost();
  const { refreshPreview } = useConversationStore();
  const events = useEventStore((state) => state.events);
  const lastEventCountRef = useRef(events.length);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Only watch for events when there's an active preview
    if (!activeHost) {
      lastEventCountRef.current = events.length;
      return;
    }

    // Check new events since last render
    const newEvents = events.slice(lastEventCountRef.current);
    lastEventCountRef.current = events.length;

    if (newEvents.length === 0) return;

    // Look for file-write related events
    const hasFileWrite = newEvents.some((event) => {
      // V1 events: check for file editor observations (completed writes)
      if ("observation" in event && event.observation) {
        const obs = event.observation as { kind?: string };
        if (
          obs.kind === "FileEditorObservation" ||
          obs.kind === "StrReplaceEditorObservation"
        ) {
          return true;
        }
      }

      // V0 events: check action type for file writes
      if ("action" in event) {
        const act = event as { action?: string; args?: { path?: string } };
        if (act.action === "write" || act.action === "edit") {
          // Optionally check if the file extension is web-related
          const filePath = act.args?.path || "";
          return WEB_FILE_PATTERNS.test(filePath) || !filePath;
        }
      }

      return false;
    });

    if (hasFileWrite) {
      // Debounce: wait 1.5s after last file write before refreshing
      // (agent often writes multiple files in quick succession)
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = setTimeout(() => {
        refreshPreview();
        debounceTimerRef.current = null;
      }, 1500);
    }
  }, [events, activeHost, refreshPreview]);

  // Cleanup on unmount
  useEffect(
    () => () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    },
    [],
  );
}
