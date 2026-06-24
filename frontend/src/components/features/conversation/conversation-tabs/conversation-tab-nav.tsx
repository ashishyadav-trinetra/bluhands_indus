import { ComponentType } from "react";
import { cn } from "#/utils/utils";

type ConversationTabNavProps = {
  tabValue: string;
  icon: ComponentType<{ className: string }>;
  onClick(): void;
  isActive?: boolean;
  label?: string;
  className?: string;
  isProminent?: boolean;
};

export function ConversationTabNav({
  tabValue,
  icon: Icon,
  onClick,
  isActive,
  label,
  className,
  isProminent,
}: ConversationTabNavProps) {
  return (
    <button
      type="button"
      onClick={() => {
        onClick();
      }}
      data-testid={`conversation-tab-${tabValue}`}
      className={cn(
        "flex items-center gap-1.5 rounded-lg cursor-pointer transition-all duration-150",
        "px-2.5 py-1.5",
        // Default state
        "text-[#9299AA]",
        // Prominent tab (App/Preview) gets special treatment
        isProminent &&
          !isActive &&
          "bg-[#3b82f6]/10 text-[#60a5fa] hover:bg-[#3b82f6]/20",
        isProminent && isActive && "bg-[#3b82f6] text-white",
        // Regular active state
        !isProminent && isActive && "bg-[#3b82f6]/15 text-[#60a5fa]",
        // Regular hover
        !isProminent && !isActive && "hover:bg-[#1e2028] hover:text-white",
        className,
      )}
    >
      <Icon
        className={cn(
          "w-4 h-4 flex-shrink-0",
          isProminent && isActive ? "text-white" : "text-inherit",
        )}
      />
      {/* Always show label */}
      {label && (
        <span
          className={cn(
            "text-xs font-medium whitespace-nowrap",
            isProminent && isActive ? "text-white" : "text-inherit",
          )}
        >
          {label}
        </span>
      )}
    </button>
  );
}
