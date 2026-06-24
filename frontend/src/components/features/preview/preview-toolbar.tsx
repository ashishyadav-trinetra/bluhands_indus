import { useTranslation } from "react-i18next";
import { FaArrowRotateRight } from "react-icons/fa6";
import { FaExternalLinkAlt, FaHome } from "react-icons/fa";
import { I18nKey } from "#/i18n/declaration";
import { cn } from "#/utils/utils";
import {
  useConversationStore,
  type PreviewViewport,
} from "#/stores/conversation-store";

interface PreviewToolbarProps {
  url: string;
  onRefresh: () => void;
  onHome: () => void;
  onUrlChange: (url: string) => void;
}

const VIEWPORT_OPTIONS: {
  value: PreviewViewport;
  label: string;
  icon: string;
  width: string;
}[] = [
  { value: "mobile", label: "Mobile", icon: "📱", width: "375px" },
  { value: "tablet", label: "Tablet", icon: "📋", width: "768px" },
  { value: "desktop", label: "Desktop", icon: "🖥", width: "100%" },
];

export function PreviewToolbar({
  url,
  onRefresh,
  onHome,
  onUrlChange,
}: PreviewToolbarProps) {
  const { t } = useTranslation();
  const { previewViewport, setPreviewViewport } = useConversationStore();

  const handleUrlSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const urlValue = formData.get("preview-url")?.toString();
    if (urlValue) {
      onUrlChange(urlValue);
    }
  };

  const handleUrlBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    const urlValue = e.target.value;
    if (urlValue) {
      onUrlChange(urlValue);
    }
  };

  return (
    <div className="flex items-center gap-2 px-3 py-2 border-b border-[#2a2d37] bg-[#111318]">
      {/* Navigation buttons */}
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onHome}
          className="p-1.5 rounded-md hover:bg-[#3A3D47] transition-colors text-[#9299AA] hover:text-white"
          aria-label={t(I18nKey.BUTTON$HOME)}
        >
          <FaHome className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={onRefresh}
          className="p-1.5 rounded-md hover:bg-[#3A3D47] transition-colors text-[#9299AA] hover:text-white"
          aria-label={t(I18nKey.BUTTON$REFRESH)}
        >
          <FaArrowRotateRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* URL bar */}
      <form
        onSubmit={handleUrlSubmit}
        className="flex-1 flex items-center bg-[#0D0F11] rounded-md border border-[#3A3D47] px-3 py-1"
      >
        {/* Connection status dot */}
        <div className="w-2 h-2 rounded-full bg-[#3b82f6] mr-2 shrink-0" />
        <input
          name="preview-url"
          type="text"
          defaultValue={url}
          key={url}
          onBlur={handleUrlBlur}
          className="w-full bg-transparent text-xs text-[#9299AA] outline-none placeholder-[#555]"
          placeholder="localhost:3000"
        />
      </form>

      {/* Viewport toggles */}
      <div className="flex items-center gap-0.5 bg-[#0D0F11] rounded-md border border-[#3A3D47] p-0.5">
        {VIEWPORT_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setPreviewViewport(option.value)}
            className={cn(
              "px-2 py-1 rounded text-xs transition-colors",
              previewViewport === option.value
                ? "bg-[#3A3D47] text-white"
                : "text-[#9299AA] hover:text-white hover:bg-[#2A2D37]",
            )}
            aria-label={option.label}
            title={`${option.label} (${option.width})`}
          >
            {option.icon}
          </button>
        ))}
      </div>

      {/* Open in new tab */}
      <button
        type="button"
        onClick={() => window.open(url, "_blank")}
        className="p-1.5 rounded-md hover:bg-[#3A3D47] transition-colors text-[#9299AA] hover:text-white"
        aria-label={t(I18nKey.BUTTON$OPEN_IN_NEW_TAB)}
      >
        <FaExternalLinkAlt className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
