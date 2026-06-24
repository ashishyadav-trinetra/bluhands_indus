import { useQuery } from "@tanstack/react-query";
import { forgeService } from "#/api/bluhands-service/forge.api";

export function useForgeMe() {
  return useQuery({
    queryKey: ["forge", "me"],
    queryFn: forgeService.me,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
