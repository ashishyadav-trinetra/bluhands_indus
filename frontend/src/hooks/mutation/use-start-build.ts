import { useMutation, useQueryClient } from "@tanstack/react-query";
import { forgeService } from "#/api/bluhands-service/forge.api";

interface StartBuildArgs {
  orgId: string;
  tenantId: string;
  prompt: string;
  idempotencyKey?: string;
  github?: {
    repo_url: string;
    push?: boolean;
    pull?: boolean;
  };
}

export function useStartBuild() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ orgId, tenantId, prompt, idempotencyKey, github }: StartBuildArgs) =>
      forgeService.startBuild(orgId, tenantId, {
        prompt,
        idempotency_key: idempotencyKey,
        ...(github?.repo_url
          ? {
              github_repo_url: github.repo_url,
              github_push: !!github.push,
              github_pull: !!github.pull,
            }
          : {}),
      }),
    onSuccess: (_data, { orgId, tenantId }) => {
      // Invalidate builds list so home screen updates.
      queryClient.invalidateQueries({
        queryKey: ["forge", "builds", orgId, tenantId],
      });
    },
  });
}
