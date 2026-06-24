import { useQuery } from "@tanstack/react-query";
import { forgeService } from "#/api/bluhands-service/forge.api";

export function useForgeTenants(orgId: string | undefined) {
  return useQuery({
    queryKey: ["forge", "tenants", orgId],
    queryFn: () => forgeService.listTenants(orgId!),
    enabled: !!orgId,
    staleTime: 60 * 1000,
  });
}
