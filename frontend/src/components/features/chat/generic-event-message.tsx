import React from "react";
import { SuccessIndicator } from "./success-indicator";
import { ObservationResultStatus } from "./event-content-helpers/get-observation-result";
import { MarkdownRenderer } from "../markdown/markdown-renderer";
import { cn } from "#/utils/utils";

interface GenericEventMessageProps {
  title: React.ReactNode;
  details: string | React.ReactNode;
  success?: ObservationResultStatus;
  initiallyExpanded?: boolean;
  chevronPosition?: "before" | "after";
  titleTrailing?: React.ReactNode;
}

export function GenericEventMessage({
  title,
  details,
  success,
  initiallyExpanded = false,
  chevronPosition = "after",
  titleTrailing,
}: GenericEventMessageProps) {
  const [showDetails, setShowDetails] = React.useState(initiallyExpanded);

  const chevronIcon = (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      className={cn(
        "transition-transform duration-150",
        showDetails && "rotate-180",
        chevronPosition === "after" ? "ml-1.5" : "mr-1.5",
      )}
    >
      <path
        d="M3 4.5L6 7.5L9 4.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );

  const chevron = details ? (
    <button
      type="button"
      onClick={() => setShowDetails((prev) => !prev)}
      className="cursor-pointer text-left text-[#666] hover:text-[#999] transition-colors"
      aria-label={showDetails ? "Collapse" : "Expand"}
    >
      {chevronIcon}
    </button>
  ) : null;

  return (
    <div
      className={cn(
        "flex flex-col gap-1.5 my-1 py-2 px-3 rounded-lg text-sm w-full transition-colors",
        "bg-[#1a1c22]/50 border border-[#2a2d37]/50",
        showDetails && "bg-[#1a1c22] border-[#2a2d37]",
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center text-[#9099ac] text-xs font-medium">
          {chevronPosition === "before" && chevron}
          <span className="truncate">{title}</span>
          {chevronPosition === "after" && chevron}
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {titleTrailing}
          {success && <SuccessIndicator status={success} />}
        </div>
      </div>

      {showDetails && (
        <div className="text-xs text-[#777] overflow-x-auto custom-scrollbar">
          {typeof details === "string" ? (
            <MarkdownRenderer>{details}</MarkdownRenderer>
          ) : (
            details
          )}
        </div>
      )}
    </div>
  );
}
