import { motion, AnimatePresence } from "framer-motion";
import { Suggestions } from "#/components/features/suggestions/suggestions";
import { useConversationStore } from "#/stores/conversation-store";
import { useSettings } from "#/hooks/query/use-settings";
import { useForgeMe } from "#/hooks/query/use-forge-me";

const STARTER_SUGGESTIONS = [
  {
    label: "Landing page",
    value:
      "Create a modern landing page with a hero section, features grid, testimonials, and a CTA. Use React with Tailwind CSS. Make it responsive. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
    icon: "🚀",
  },
  {
    label: "E-commerce store",
    value:
      "Build an e-commerce store with a product catalog, shopping cart, and checkout page. Use Node.js with Express and Tailwind CSS. No payment processing yet. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
    icon: "🛍️",
  },
  {
    label: "Dashboard",
    value:
      "Create an analytics dashboard with charts, stat cards, and a sidebar navigation. Use React with Tailwind CSS and Recharts for the charts. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
    icon: "📊",
  },
  {
    label: "REST API",
    value:
      "Build a REST API with Express.js and a PostgreSQL database. Include user CRUD endpoints, authentication middleware, and proper error handling. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
    icon: "⚡",
  },
  {
    label: "Portfolio site",
    value:
      "Build a personal portfolio website with an about section, project showcase, skills, and contact form. Use a clean modern design with Tailwind CSS. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
    icon: "✨",
  },
  {
    label: "Full-stack app",
    value:
      "Build a full-stack todo app with a React frontend, Express backend, and a SQLite database. Include user authentication, CRUD operations, and real-time updates. Use port 8011 and bind to 0.0.0.0 (not localhost) for the server so it is accessible externally.",
    icon: "🏗️",
  },
];

interface ChatSuggestionsProps {
  onSuggestionsClick: (value: string) => void;
}

export function ChatSuggestions({ onSuggestionsClick }: ChatSuggestionsProps) {
  const { shouldHideSuggestions } = useConversationStore();
  const { data: settings } = useSettings();
  const { data: forgeMe } = useForgeMe();

  const userName =
    forgeMe?.full_name ||
    forgeMe?.display_name ||
    forgeMe?.email?.split("@")[0] ||
    settings?.git_user_name ||
    "there";
  const firstName = userName.split(" ")[0];

  return (
    <AnimatePresence>
      {!shouldHideSuggestions && (
        <motion.div
          data-testid="chat-suggestions"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="absolute top-0 left-0 right-0 bottom-[151px] flex flex-col items-center justify-center pointer-events-auto overflow-hidden"
        >
          {/* Gradient backdrop */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background: `
                radial-gradient(ellipse 100% 80% at 50% -10%, rgba(59, 130, 246, 0.30) 0%, transparent 50%),
                radial-gradient(ellipse 70% 60% at 85% 20%, rgba(168, 85, 247, 0.20) 0%, transparent 50%),
                radial-gradient(ellipse 60% 50% at 60% 90%, rgba(236, 72, 153, 0.15) 0%, transparent 50%)
              `,
            }}
          />

          {/* Content */}
          <div className="relative z-10 flex flex-col items-center w-full max-w-[560px] px-4">
            {/* Personalized greeting */}
            <motion.h1
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1, duration: 0.4 }}
              className="text-[28px] font-semibold text-white mb-2 text-center"
            >
              Let&apos;s build something,{" "}
              <span className="bg-gradient-to-r from-[#3b82f6] to-[#a855f7] bg-clip-text text-transparent">
                {firstName}
              </span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.4 }}
              className="text-sm text-[#666] mb-8 text-center"
            >
              Describe your project or pick a starter below
            </motion.p>

            {/* Suggestion grid */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.4 }}
              className="w-full"
            >
              <Suggestions
                suggestions={STARTER_SUGGESTIONS}
                onSuggestionClick={onSuggestionsClick}
              />
            </motion.div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
