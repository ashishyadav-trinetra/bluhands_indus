import { useQuery } from "@tanstack/react-query";
import { forgeService } from "#/api/bluhands-service/forge.api";

/** Whether the user has connected GitHub (via Nango). */
export function useGithubStatus() {
  return useQuery({
    queryKey: ["forge", "github", "status"],
    queryFn: forgeService.githubStatus,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

/** The connected user's repositories (only fetched when connected). */
export function useGithubRepos(enabled: boolean) {
  return useQuery({
    queryKey: ["forge", "github", "repos"],
    queryFn: forgeService.githubRepos,
    enabled,
    staleTime: 60 * 1000,
    retry: 1,
  });
}
