import { useQuery } from "@tanstack/react-query";
import SettingsService from "#/api/settings-service/settings-service.api";
import { useIsOnIntermediatePage } from "#/hooks/use-is-on-intermediate-page";
import { SettingsSchema } from "#/types/settings";
import { useIsAuthed } from "./use-is-authed";

const hasValidSections = (s?: SettingsSchema | null) =>
  Boolean(s && Array.isArray(s.sections) && s.sections.length > 0);

const useSettingsSchema = (
  type: "agent" | "conversation",
  fallbackSchema?: SettingsSchema | null,
) => {
  const isOnIntermediatePage = useIsOnIntermediatePage();
  const validFallback = hasValidSections(fallbackSchema) ? fallbackSchema : null;

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["settings-schema", type],
    queryFn:
      type === "conversation"
        ? SettingsService.getConversationSettingsSchema
        : SettingsService.getSettingsSchema,
    retry: 2,
    refetchOnWindowFocus: false,
    staleTime: 0,
    gcTime: 1000 * 60 * 15,
    enabled: !validFallback && !isOnIntermediatePage,
    meta: {
      disableToast: true,
    },
  });

  if (validFallback) {
    return {
      data: validFallback,
      isLoading: false,
      isFetching: false,
    };
  }

  return {
    data,
    isLoading,
    isFetching,
  };
};

export const useAgentSettingsSchema = (
  fallbackSchema?: SettingsSchema | null,
) => useSettingsSchema("agent", fallbackSchema);

export const useConversationSettingsSchema = (
  fallbackSchema?: SettingsSchema | null,
) => useSettingsSchema("conversation", fallbackSchema);
