import { cn } from "#/utils/utils";

const FOLLOW_UP_CHIPS = [
  { label: "Improve the styling", icon: "🎨" },
  { label: "Add dark mode", icon: "🌙" },
  { label: "Make it responsive", icon: "📱" },
  { label: "Add more pages", icon: "📄" },
  { label: "Add authentication", icon: "🔐" },
  { label: "Connect a database", icon: "🗄️" },
];

interface FollowUpSuggestionsProps {
  onSuggestionClick: (message: string) => void;
  className?: string;
}

export function FollowUpSuggestions({
  onSuggestionClick,
  className,
}: FollowUpSuggestionsProps) {
  return (
    <div className={cn("flex flex-wrap gap-2 px-4 pb-2", className)}>
      {FOLLOW_UP_CHIPS.map((chip) => (
        <button
          key={chip.label}
          type="button"
          onClick={() => onSuggestionClick(chip.label)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#2a2d37]/60 bg-[#111318]/60 backdrop-blur-sm text-xs text-[#9099ac] hover:border-[#3b82f6]/30 hover:text-white hover:bg-[#1a1c22]/80 transition-all duration-200 cursor-pointer"
        >
          <span className="text-sm">{chip.icon}</span>
          <span>{chip.label}</span>
        </button>
      ))}
    </div>
  );
}
