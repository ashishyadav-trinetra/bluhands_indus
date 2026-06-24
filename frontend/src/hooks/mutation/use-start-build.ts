import { useMutation, useQueryClient } from "@tanstack/react-query";
import { forgeService } from "#/api/bluhands-service/forge.api";

interface StartBuildArgs {
  orgId: string;
  tenantId: string;
  prompt: string;
  idempotencyKey?: string;
}

export function useStartBuild() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ orgId, tenantId, prompt, idempotencyKey }: StartBuildArgs) =>
      forgeService.startBuild(orgId, tenantId, {
        prompt,
        idempotency_key: idempotencyKey,
      }),
    onSuccess: (_data, { orgId, tenantId }) => {
      // Invalidate builds list so home screen updates.
      queryClient.invalidateQueries({
        queryKey: ["forge", "builds", orgId, tenantId],
      });
    },
  });
}
