/* eslint-disable i18next/no-literal-string, jsx-a11y/control-has-associated-label */
import React from "react";
import { NavLink, useLocation, useNavigate, useParams } from "react-router";
import { useTranslation } from "react-i18next";
import { useLocalStorage } from "@uidotdev/usehooks";
import { useGitUser } from "#/hooks/query/use-git-user";
import { useForgeMe } from "#/hooks/query/use-forge-me";
import { UserActions } from "./user-actions";
import { SettingsModal } from "#/components/shared/modals/settings/settings-modal";
import { useSettings } from "#/hooks/query/use-settings";
import { useConfig } from "#/hooks/query/use-config";
import { displayErrorToast } from "#/utils/custom-toast-handlers";
import { I18nKey } from "#/i18n/declaration";
import { cn } from "#/utils/utils";
import { usePaginatedConversations } from "#/hooks/query/use-paginated-conversations";
import { useStartTasks } from "#/hooks/query/use-start-tasks";
import { useInfiniteScroll } from "#/hooks/use-infinite-scroll";
import { ConversationPanel } from "../conversation-panel/conversation-panel";
import { ConversationPanelWrapper } from "../conversation-panel/conversation-panel-wrapper";
import { ConversationPanelButton } from "#/components/shared/buttons/conversation-panel-button";
import { OpenHandsLogoButton } from "#/components/shared/buttons/openhands-logo-button";
import { NewProjectButton } from "#/components/shared/buttons/new-project-button";
import { ENABLE_AUTOMATIONS } from "#/utils/feature-flags";
import { AutomationsButton } from "#/components/shared/buttons/automations-button";

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function Sidebar() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { conversationId: currentConversationId } = useParams();
  const user = useGitUser();
  const { data: forgeMe } = useForgeMe();
  const { data: config } = useConfig();
  const {
    data: settings,
    error: settingsError,
    isError: settingsIsError,
    isFetching: isFetchingSettings,
  } = useSettings();

  const [settingsModalIsOpen, setSettingsModalIsOpen] = React.useState(false);
  const [isSidebarExpanded, setIsSidebarExpanded] = useLocalStorage(
    "sidebar-expanded",
    true,
  );
  const [searchQuery, setSearchQuery] = React.useState("");

  // Admin check — show admin link only for platform admins
  const [isAdmin, setIsAdmin] = React.useState(false);
  React.useEffect(() => {
    import("#/api/bluhands-service/forge-axios").then(({ forgeClient }) => {
      forgeClient
        .get<{ data: { user: { is_platform_admin: boolean } } }>("/api/v1/auth/me")
        .then((r) => setIsAdmin(r.data?.data?.user?.is_platform_admin === true))
        .catch(() => {});
    });
  }, []);

  // Conversation panel for collapsed mode
  const [conversationPanelIsOpen, setConversationPanelIsOpen] =
    React.useState(false);

  // Fetch conversations for the inline list
  const {
    data: conversationData,
    isFetching: isFetchingConversations,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  } = usePaginatedConversations();

  const { data: startTasks } = useStartTasks();

  const conversations =
    conversationData?.pages.flatMap((page) => page.items) ?? [];

  const filteredConversations = searchQuery
    ? conversations.filter((c) =>
        (c.title || "").toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : conversations;

  const scrollContainerRef = useInfiniteScroll({
    hasNextPage: !!hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
    threshold: 200,
  });

  React.useEffect(() => {
    if (pathname === "/settings") {
      setSettingsModalIsOpen(false);
    } else if (
      !isFetchingSettings &&
      settingsIsError &&
      settingsError?.status !== 404
    ) {
      displayErrorToast(
        "Something went wrong while fetching settings. Please reload the page.",
      );
    }
    // NOTE: we intentionally do NOT force-open the "AI Provider Configuration"
    // modal on a 404. On BluHands the platform provides the model (per-user
    // default), so a user with no settings yet must not be hard-blocked by a
    // non-bypassable popup. Users who want to bring their own key open it
    // themselves via Settings -> LLM.
  }, [
    pathname,
    isFetchingSettings,
    settingsIsError,
    settingsError,
    config?.app_mode,
    config?.feature_flags?.hide_llm_settings,
  ]);

  // Get user display name/initials
  const userName =
    forgeMe?.full_name ||
    forgeMe?.display_name ||
    forgeMe?.email?.split("@")[0] ||
    settings?.git_user_name ||
    user.data?.login ||
    "User";
  const userInitials = userName
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  if (!isSidebarExpanded) {
    // Collapsed mode: thin icon sidebar (similar to original)
    return (
      <>
        <aside
          aria-label={t(I18nKey.SIDEBAR$NAVIGATION_LABEL)}
          className="hidden md:flex flex-col items-center w-[60px] min-w-[60px] bg-[#111318] border-r border-[#1e2028] py-3 gap-1"
        >
          <nav className="flex flex-col items-center justify-between w-full h-full">
            <div className="flex flex-col items-center gap-5">
              {/* Logo */}
              <button
                type="button"
                onClick={() => navigate("/")}
                className="w-8 h-8 rounded-lg overflow-hidden flex items-center justify-center shrink-0"
              >
                <img
                  src="/blu-hands-logo.png.png"
                  alt="Blu Hands"
                  className="w-8 h-8 object-cover"
                />
              </button>
              {/* New project */}
              <button
                type="button"
                onClick={() => navigate("/")}
                className="w-8 h-8 rounded-lg bg-[#1e2028] hover:bg-[#2a2d37] flex items-center justify-center text-[#9099ac] hover:text-white transition-colors"
                title="New project"
              >
                <svg
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <line x1="8" y1="3" x2="8" y2="13" />
                  <line x1="3" y1="8" x2="13" y2="8" />
                </svg>
              </button>
              {/* Conversations */}
              <ConversationPanelButton
                isOpen={conversationPanelIsOpen}
                onClick={() =>
                  settings?.email_verified === false
                    ? null
                    : setConversationPanelIsOpen((prev) => !prev)
                }
                disabled={settings?.email_verified === false}
              />
              {ENABLE_AUTOMATIONS() && (
                <AutomationsButton
                  disabled={settings?.email_verified === false}
                />
              )}
            </div>

            <div className="flex flex-col items-center gap-5">
              {/* Upgrade to Pro — collapsed */}
              <button
                type="button"
                onClick={() => navigate("/pricing")}
                className="w-8 h-8 rounded-lg bg-[#7C3AED]/20 border border-[#7C3AED]/30 hover:bg-[#7C3AED]/30 flex items-center justify-center transition-colors"
                title="Upgrade to Pro"
              >
                <span className="text-sm">⚡</span>
              </button>
              {/* Expand button */}
              <button
                type="button"
                onClick={() => setIsSidebarExpanded(true)}
                className="w-8 h-8 rounded-lg hover:bg-[#1e2028] flex items-center justify-center text-[#666] hover:text-white transition-colors"
                title="Expand sidebar"
              >
                <svg
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path d="M6 3l5 5-5 5" />
                </svg>
              </button>
              {/* User */}
              <UserActions
                user={
                  user.data ? { avatar_url: user.data.avatar_url } : undefined
                }
                isLoading={user.isFetching}
              />
            </div>
          </nav>

          {conversationPanelIsOpen && (
            <ConversationPanelWrapper isOpen={conversationPanelIsOpen}>
              <ConversationPanel
                onClose={() => setConversationPanelIsOpen(false)}
              />
            </ConversationPanelWrapper>
          )}
        </aside>

        {/* Mobile: keep original horizontal bar */}
        <aside
          aria-label={t(I18nKey.SIDEBAR$NAVIGATION_LABEL)}
          className="md:hidden h-[54px] p-3 flex flex-row gap-1 bg-base"
        >
          <nav className="flex flex-row items-center justify-between w-full">
            <div className="flex flex-row items-center gap-[26px]">
              <OpenHandsLogoButton />
              <NewProjectButton disabled={settings?.email_verified === false} />
              <ConversationPanelButton
                isOpen={conversationPanelIsOpen}
                onClick={() =>
                  settings?.email_verified === false
                    ? null
                    : setConversationPanelIsOpen((prev) => !prev)
                }
                disabled={settings?.email_verified === false}
              />
            </div>
            <UserActions
              user={
                user.data ? { avatar_url: user.data.avatar_url } : undefined
              }
              isLoading={user.isFetching}
            />
          </nav>
          {conversationPanelIsOpen && (
            <ConversationPanelWrapper isOpen={conversationPanelIsOpen}>
              <ConversationPanel
                onClose={() => setConversationPanelIsOpen(false)}
              />
            </ConversationPanelWrapper>
          )}
        </aside>

        {settingsModalIsOpen && (
          <SettingsModal
            settings={settings}
            onClose={() => setSettingsModalIsOpen(false)}
          />
        )}
      </>
    );
  }

  // Expanded mode: full sidebar
  return (
    <>
      {/* Mobile: keep original horizontal bar */}
      <aside
        aria-label={t(I18nKey.SIDEBAR$NAVIGATION_LABEL)}
        className="md:hidden h-[54px] p-3 flex flex-row gap-1 bg-base"
      >
        <nav className="flex flex-row items-center justify-between w-full">
          <div className="flex flex-row items-center gap-[26px]">
            <OpenHandsLogoButton />
            <NewProjectButton disabled={settings?.email_verified === false} />
            <ConversationPanelButton
              isOpen={conversationPanelIsOpen}
              onClick={() =>
                settings?.email_verified === false
                  ? null
                  : setConversationPanelIsOpen((prev) => !prev)
              }
              disabled={settings?.email_verified === false}
            />
          </div>
          <UserActions
            user={user.data ? { avatar_url: user.data.avatar_url } : undefined}
            isLoading={user.isFetching}
          />
        </nav>
        {conversationPanelIsOpen && (
          <ConversationPanelWrapper isOpen={conversationPanelIsOpen}>
            <ConversationPanel
              onClose={() => setConversationPanelIsOpen(false)}
            />
          </ConversationPanelWrapper>
        )}
      </aside>

      {/* Desktop: expanded sidebar */}
      <aside
        aria-label={t(I18nKey.SIDEBAR$NAVIGATION_LABEL)}
        className="hidden md:flex flex-col w-[260px] min-w-[260px] bg-[#111318] border-r border-[#1e2028]"
      >
        {/* Logo + brand + collapse */}
        <div className="flex items-center gap-2.5 px-4 pt-4 pb-3">
          <button
            type="button"
            onClick={() => navigate("/")}
            className="w-8 h-8 rounded-lg overflow-hidden flex items-center justify-center shrink-0"
          >
            <img
              src="/blu-hands-logo.png.png"
              alt="Blu Hands"
              className="w-8 h-8 object-cover"
            />
          </button>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white leading-tight">
              Blu Hands
            </p>
            <p className="text-[11px] text-[#666] leading-tight">
              code less, make more
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsSidebarExpanded(false)}
            className="w-6 h-6 rounded flex items-center justify-center text-[#555] hover:text-white hover:bg-[#1e2028] transition-colors shrink-0"
            title="Collapse sidebar"
          >
            <svg
              width="14"
              height="14"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M9 3L4 7l5 4" />
            </svg>
          </button>
        </div>

        {/* New project button */}
        <div className="px-3 mb-3">
          <button
            type="button"
            onClick={() => {
              if (settings?.email_verified !== false) {
                navigate("/");
              }
            }}
            disabled={settings?.email_verified === false}
            className="w-full bg-[#3b82f6] hover:bg-[#2563eb] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg py-2.5 px-3.5 flex items-center gap-2 transition-colors"
          >
            <svg
              width="16"
              height="16"
              fill="none"
              stroke="white"
              strokeWidth="2.5"
            >
              <line x1="8" y1="3" x2="8" y2="13" />
              <line x1="3" y1="8" x2="13" y2="8" />
            </svg>
            <span className="text-[13px] font-medium text-white">
              New project
            </span>
          </button>
        </div>

        {/* Navigation links */}
        <div className="px-2 mb-2">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-xl px-3.5 py-2.5 mb-1 text-[13px] font-medium transition-colors",
                isActive
                  ? "bg-[#1e2028] text-white"
                  : "text-[#6b7280] hover:bg-[#1a1c22] hover:text-[#e2e8f0]",
              )
            }
          >
            <svg
              width="16"
              height="16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              className="shrink-0"
            >
              <path d="M2 5.5L7.5 1 13 5.5V12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5.5z" />
              <path d="M5 13V7h5v6" />
            </svg>
            Home
          </NavLink>
          <NavLink
            to="/connectors"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-xl px-3.5 py-2.5 mb-1 text-[13px] font-medium transition-colors",
                isActive
                  ? "bg-[#1e2028] text-white"
                  : "text-[#6b7280] hover:bg-[#1a1c22] hover:text-[#e2e8f0]",
              )
            }
          >
            <svg
              width="16"
              height="16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              className="shrink-0"
            >
              <circle cx="8" cy="8" r="2.2" />
              <path d="M1.5 8h4M10.5 8h4M8 1.5v4M8 10.5v4" />
            </svg>
            Connectors
          </NavLink>
        </div>

        {/* Search */}
        <div className="px-3 mb-3">
          <div className="flex items-center gap-2 bg-[#1a1c22]/60 border border-[#2a2d37]/60 rounded-lg px-3 py-2">
            <svg
              width="14"
              height="14"
              fill="none"
              stroke="#555"
              strokeWidth="1.5"
              className="shrink-0"
            >
              <circle cx="6" cy="6" r="5" />
              <line x1="10" y1="10" x2="13" y2="13" />
            </svg>
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent text-xs text-white placeholder-[#555] outline-none w-full"
            />
            <kbd className="hidden lg:inline text-[10px] text-[#444] bg-[#1e2028] px-1.5 py-0.5 rounded border border-[#2a2d37] font-mono">
              /
            </kbd>
          </div>
        </div>

        {/* Section label */}
        <div className="px-4 mb-1.5">
          <p className="text-[11px] font-medium text-[#444] uppercase tracking-wider">
            Recents
          </p>
        </div>

        {/* Conversation list */}
        <div
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto px-2 custom-scrollbar"
        >
          {isFetchingConversations && conversations.length === 0 && (
            <div className="flex items-center justify-center py-8">
              <div className="w-5 h-5 border-2 border-[#333] border-t-[#3b82f6] rounded-full animate-spin" />
            </div>
          )}

          {!isFetchingConversations &&
            conversations.length === 0 &&
            !startTasks?.length && (
              <div className="flex items-center justify-center py-8">
                <p className="text-xs text-[#555]">No conversations yet</p>
              </div>
            )}

          {/* Start tasks */}
          {startTasks?.map((task) => (
            <NavLink
              key={task.id}
              to={`/conversations/task-${task.id}`}
              className="block rounded-lg px-3 py-2.5 mb-1 bg-[#1e2028] border-l-[3px] border-[#3b82f6] animate-pulse"
            >
              <p className="text-xs font-medium text-white truncate">
                Starting...
              </p>
              <p className="text-[11px] text-[#555] mt-0.5">Just now</p>
            </NavLink>
          ))}

          {/* Conversations */}
          {filteredConversations.map((conversation) => {
            const isActive = currentConversationId === conversation.id;
            return (
              <NavLink
                key={conversation.id}
                to={`/conversations/${conversation.id}`}
                className={cn(
                  "block rounded-lg px-3 py-2.5 mb-1 transition-colors",
                  isActive
                    ? "bg-[#1e2028] border-l-[3px] border-[#3b82f6]"
                    : "border-l-[3px] border-transparent hover:bg-[#1a1c22]",
                )}
              >
                <p
                  className={cn(
                    "text-xs truncate",
                    isActive ? "font-medium text-white" : "text-[#9099ac]",
                  )}
                >
                  {conversation.title || "Untitled"}
                </p>
                <p className="text-[11px] text-[#555] mt-0.5">
                  {conversation.updated_at
                    ? formatRelativeTime(conversation.updated_at)
                    : ""}
                </p>
              </NavLink>
            );
          })}

          {isFetchingNextPage && (
            <div className="flex justify-center py-3">
              <div className="w-4 h-4 border-2 border-[#333] border-t-[#3b82f6] rounded-full animate-spin" />
            </div>
          )}
        </div>

        {/* Bottom section */}
        <div className="border-t border-[#1e2028] px-2 py-2">
          {/* Upgrade to Pro CTA — always visible */}
          <NavLink
            to="/pricing"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2.5 mb-2 bg-gradient-to-r from-[#7C3AED]/20 to-[#2563EB]/20 border border-[#7C3AED]/30 hover:from-[#7C3AED]/30 hover:to-[#2563EB]/30 transition-all group"
          >
            <span className="flex h-5 w-5 items-center justify-center rounded-md bg-[#7C3AED] text-white text-[10px] font-bold shrink-0">
              ⚡
            </span>
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-white">
                Upgrade to Pro
              </span>
              <span className="text-[10px] text-[#9099ac] group-hover:text-[#b0b8c8]">
                Unlock more features
              </span>
            </div>
          </NavLink>

          {/* Admin Panel — only visible to super admins */}
          {isAdmin && (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 mb-1 transition-colors",
                  isActive
                    ? "bg-[#1e2028] text-white"
                    : "text-[#9099ac] hover:bg-[#1a1c22] hover:text-white",
                )
              }
            >
              <svg
                width="16"
                height="16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="shrink-0"
              >
                <rect x="2" y="2" width="5" height="5" rx="1" />
                <rect x="9" y="2" width="5" height="5" rx="1" />
                <rect x="2" y="9" width="5" height="5" rx="1" />
                <rect x="9" y="9" width="5" height="5" rx="1" />
              </svg>
              <span className="text-xs">Admin</span>
            </NavLink>
          )}

          {/* Settings */}
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 mb-1 transition-colors",
                isActive
                  ? "bg-[#1e2028] text-white"
                  : "text-[#9099ac] hover:bg-[#1a1c22] hover:text-white",
              )
            }
          >
            <svg
              width="16"
              height="16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="shrink-0"
            >
              <circle cx="8" cy="8" r="3" />
              <path d="M8 1v2M8 13v2M1 8h2M13 8h2M2.9 2.9l1.4 1.4M11.7 11.7l1.4 1.4M2.9 13.1l1.4-1.4M11.7 4.3l1.4-1.4" />
            </svg>
            <span className="text-xs">Settings</span>
          </NavLink>

          {/* User profile + logout */}
          <div className="flex items-center gap-2.5 rounded-lg px-3 py-2 group">
            <div className="w-6 h-6 rounded-full bg-[#2a2d37] flex items-center justify-center shrink-0">
              {user.data?.avatar_url ? (
                <img
                  src={user.data.avatar_url}
                  alt="avatar"
                  className="w-6 h-6 rounded-full"
                />
              ) : (
                <span className="text-[10px] font-medium text-[#3b82f6]">
                  {userInitials}
                </span>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-white truncate">{userName}</p>
            </div>
            {import.meta.env.VITE_SUPABASE_URL && (
              <button
                type="button"
                onClick={async () => {
                  const { supabase } = await import("#/lib/supabase");
                  await supabase?.auth.signOut();
                  window.location.href = "/login";
                }}
                className="opacity-0 group-hover:opacity-100 text-[#666] hover:text-red-400 transition-all"
                title="Sign out"
              >
                <svg
                  width="14"
                  height="14"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path d="M5 1H3a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2M8 10l3-3-3-3M4 7h7" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </aside>

      {settingsModalIsOpen && (
        <SettingsModal
          settings={settings}
          onClose={() => setSettingsModalIsOpen(false)}
        />
      )}
    </>
  );
}
