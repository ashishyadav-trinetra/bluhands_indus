import React from "react";
import { useTranslation } from "react-i18next";
import { useUnifiedActiveHost } from "#/hooks/query/use-unified-active-host";
import { useConversationStore } from "#/stores/conversation-store";
import { I18nKey } from "#/i18n/declaration";
import { PreviewToolbar } from "./preview-toolbar";
import ServerProcessIcon from "#/icons/server-process.svg?react";
import { cn } from "#/utils/utils";

const VIEWPORT_WIDTHS: Record<string, number | null> = {
  mobile: 375,
  tablet: 768,
  desktop: null, // null = 100%
};

export function PreviewPanel() {
  const { t } = useTranslation();
  const { activeHost } = useUnifiedActiveHost();
  const { previewViewport, previewRefreshKey } = useConversationStore();

  const [currentActiveHost, setCurrentActiveHost] = React.useState<
    string | null
  >(null);
  const [path, setPath] = React.useState<string>("");
  const [localRefreshKey, setLocalRefreshKey] = React.useState(0);

  const iframeContainerRef = React.useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = React.useState<number>(0);

  // Track container width for viewport scaling
  React.useEffect(() => {
    if (!iframeContainerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });

    observer.observe(iframeContainerRef.current);
    return () => observer.disconnect();
  }, []);

  // Sync with discovered active host
  React.useEffect(() => {
    if (activeHost) {
      setCurrentActiveHost(activeHost);
      setPath("");
    }
  }, [activeHost]);

  // Respond to store-triggered refreshes (from hot-reload)
  React.useEffect(() => {
    if (previewRefreshKey > 0) {
      setLocalRefreshKey((prev) => prev + 1);
    }
  }, [previewRefreshKey]);

  const handleRefresh = () => {
    setLocalRefreshKey((prev) => prev + 1);
  };

  const handleHome = () => {
    setCurrentActiveHost(activeHost);
    setPath("");
  };

  const handleUrlChange = (newUrl: string) => {
    try {
      const parsed = new URL(newUrl);
      setCurrentActiveHost(parsed.origin);
      setPath(parsed.pathname.replace(/^\//, ""));
    } catch {
      // If not a valid URL, treat as path
      setPath(newUrl);
    }
  };

  const fullUrl = currentActiveHost
    ? `${currentActiveHost}${path ? `/${path}` : ""}`
    : "";

  // Calculate viewport scaling
  const viewportWidth = VIEWPORT_WIDTHS[previewViewport];
  const needsScaling =
    viewportWidth !== null &&
    containerWidth > 0 &&
    viewportWidth < containerWidth;
  const inverseScale =
    needsScaling && viewportWidth ? viewportWidth / containerWidth : 1;

  if (!currentActiveHost) {
    return (
      <div className="flex flex-col h-full w-full">
        <div className="flex flex-col items-center justify-center flex-1 p-10">
          <ServerProcessIcon width={80} height={80} color="#555" />
          <span className="text-[#8D95A9] text-sm font-normal leading-5 mt-4 text-center">
            {t(I18nKey.BROWSER$SERVER_MESSAGE)}
          </span>
          <span className="text-[#555] text-xs mt-2 text-center">
            Preview will appear automatically when a server starts
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full">
      <PreviewToolbar
        url={fullUrl}
        onRefresh={handleRefresh}
        onHome={handleHome}
        onUrlChange={handleUrlChange}
      />

      {/* Iframe container with viewport simulation */}
      <div
        ref={iframeContainerRef}
        className="flex-1 overflow-hidden relative bg-white"
      >
        <div
          className={cn("h-full", previewViewport !== "desktop" && "mx-auto")}
          style={
            previewViewport !== "desktop" && viewportWidth
              ? {
                  width: `${viewportWidth}px`,
                  transform: needsScaling
                    ? `scale(${inverseScale})`
                    : undefined,
                  transformOrigin: "top center",
                  height: needsScaling ? `${100 / inverseScale}%` : "100%",
                }
              : { width: "100%", height: "100%" }
          }
        >
          <iframe
            key={localRefreshKey}
            title={t(I18nKey.SERVED_APP$TITLE)}
            src={fullUrl}
            className="w-full h-full border-0"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
          />
        </div>
      </div>
    </div>
  );
}
