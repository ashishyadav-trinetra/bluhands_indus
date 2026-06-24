import { useQueries, useQuery } from "@tanstack/react-query";
import React from "react";
import { useConversationId } from "#/hooks/use-conversation-id";
import { useRuntimeIsReady } from "#/hooks/use-runtime-is-ready";
import { useActiveConversation } from "#/hooks/query/use-active-conversation";
import { useBatchSandboxes } from "./use-batch-sandboxes";

/**
 * Unified hook to get active web host for both legacy (V0) and V1 conversations
 * - V0: Uses the legacy getWebHosts API endpoint and polls them
 * - V1: Gets worker URLs from sandbox exposed_urls (WORKER_1, WORKER_2, etc.)
 */
export const useUnifiedActiveHost = () => {
  const [activeHost, setActiveHost] = React.useState<string | null>(null);
  const { conversationId } = useConversationId();
  const runtimeIsReady = useRuntimeIsReady();
  const { data: conversation, isLoading: isLoadingConversation } =
    useActiveConversation();
  const sandboxId = conversation?.sandbox_id;

  // Fetch sandbox data for V1 conversations
  const sandboxesQuery = useBatchSandboxes(sandboxId ? [sandboxId] : []);
  const sandbox = sandboxesQuery?.data?.[0];

  // Get worker URLs from V1 sandbox or legacy web hosts from V0
  const { data, isLoading: hostsQueryLoading } = useQuery({
    queryKey: [conversationId, "hosts", sandbox],
    queryFn: async () => {
      // V1: Get worker URLs from sandbox exposed_urls
      if (!sandbox) {
        return { hosts: [] };
      }

      // Ports reserved by the enterprise server itself — never preview these.
      const RESERVED_PORTS = new Set([3000, 3001]);
      const workerUrls =
        sandbox.exposed_urls
          ?.filter((url) => url.name.startsWith("WORKER_"))
          .map((url) => url.url)
          .filter((url) => {
            try {
              const port = parseInt(new URL(url).port, 10);
              return !RESERVED_PORTS.has(port);
            } catch {
              return true;
            }
          }) || [];

      return { hosts: workerUrls };
    },
    enabled: runtimeIsReady && !!conversationId && !!sandboxesQuery.data,
    initialData: { hosts: [] },
    meta: {
      disableToast: true,
    },
  });

  // Poll all hosts to find which one is active
  // We use fetch with no-cors mode because the served app likely doesn't have
  // CORS headers. An "opaque" response (type === "opaque") still means the
  // server is alive and reachable — only a network error means it's down.
  const apps = useQueries({
    queries: data.hosts.map((host) => ({
      queryKey: [conversationId, "unified", "hosts", host],
      queryFn: async () => {
        try {
          await fetch(host, {
            mode: "no-cors",
            cache: "no-store",
          });
          // Any response (even opaque from no-cors) means server is alive
          return host;
        } catch {
          // Network error = server is down or unreachable
          return "";
        }
      },
      refetchInterval: 3000,
      meta: {
        disableToast: true,
      },
    })),
  });

  const appsData = apps.map((app) => app.data);

  React.useEffect(() => {
    const successfulApp = appsData.find((app) => app);
    setActiveHost(successfulApp || "");
  }, [appsData]);

  // Calculate overall loading state including dependent queries for V1
  const isLoading =
    isLoadingConversation || sandboxesQuery.isLoading || hostsQueryLoading;

  return { activeHost, isLoading };
};
