import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";

export type Suggestion = {
  label: I18nKey | string;
  value: string;
  icon?: string;
};

interface SuggestionItemProps {
  suggestion: Suggestion;
  onClick: (value: string) => void;
}

export function SuggestionItem({ suggestion, onClick }: SuggestionItemProps) {
  const { t } = useTranslation();

  return (
    <button
      type="button"
      className="group relative border border-[#2a2d37]/60 rounded-xl hover:border-[#3b82f6]/30 bg-[#111318]/60 backdrop-blur-sm hover:bg-[#1a1c22]/80 flex flex-col items-start gap-1.5 cursor-pointer p-3.5 transition-all duration-200 text-left"
      onClick={() => onClick(suggestion.value)}
    >
      {suggestion.icon && <span className="text-lg">{suggestion.icon}</span>}
      <span
        data-testid="suggestion"
        className="text-[13px] font-medium leading-5 text-[#9099ac] group-hover:text-white transition-colors"
      >
        {t(suggestion.label)}
      </span>
    </button>
  );
}
