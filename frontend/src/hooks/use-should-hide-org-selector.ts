import { useOrganizations } from "#/hooks/query/use-organizations";
import { useConfig } from "#/hooks/query/use-config";

export function useShouldHideOrgSelector() {
  const { data: config } = useConfig();
  const { data } = useOrganizations();
  const organizations = data?.organizations;

  // Always hide in OSS mode - organizations are a SaaS feature
  if (config?.app_mode === "oss") {
    return true;
  }

  // Hide the selector whenever there's nothing meaningful to choose: BluHands
  // doesn't use OpenHands' org concept, so the list is empty or a single
  // (personal) org. A picker needs >= 2 options to be useful — otherwise it just
  // shows the confusing "Please select an organization / No options" wall.
  return !organizations || organizations.length <= 1;
}
