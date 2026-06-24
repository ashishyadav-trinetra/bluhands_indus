/* eslint-disable i18next/no-literal-string, no-nested-ternary */
import React from "react";
import { useNavigate } from "react-router";
import { supabase } from "#/lib/supabase";
import { cn } from "#/utils/utils";

type AuthMode = "login" | "signup";

export function SupabaseLogin() {
  const navigate = useNavigate();
  const [mode, setMode] = React.useState<AuthMode>("login");

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [successMessage, setSuccessMessage] = React.useState<string | null>(
    null,
  );

  // Check if already logged in
  React.useEffect(() => {
    supabase?.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        navigate("/", { replace: true });
      }
    });
  }, [navigate]);

  // Sync Supabase user to local DB then navigate home
  const syncAndNavigate = React.useCallback(
    async (accessToken: string) => {
      try {
        await fetch("/api/auth/sync-user", {
          method: "POST",
          headers: { Authorization: `Bearer ${accessToken}` },
        });
      } catch {
        // Non-fatal — user already exists or DB is briefly unavailable
      }
      navigate("/", { replace: true });
    },
    [navigate],
  );

  // Listen for auth state changes
  React.useEffect(() => {
    const {
      data: { subscription },
    } = supabase!.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_IN" && session?.access_token) {
        syncAndNavigate(session.access_token);
      }
    });
    return () => subscription.unsubscribe();
  }, [navigate, syncAndNavigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);
    setLoading(true);

    try {
      if (mode === "signup") {
        const { error: signUpError } = await supabase!.auth.signUp({
          email,
          password,
        });
        if (signUpError) throw signUpError;
        setSuccessMessage("Check your email for a confirmation link!");
      } else {
        const { error: signInError } = await supabase!.auth.signInWithPassword({
          email,
          password,
        });
        if (signInError) throw signInError;
        // onAuthStateChange will handle redirect
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An error occurred";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setError(null);
    const { error: oauthError } = await supabase!.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/`,
      },
    });
    if (oauthError) setError(oauthError.message);
  };

  const handleGitHubLogin = async () => {
    setError(null);
    const { error: oauthError } = await supabase!.auth.signInWithOAuth({
      provider: "github",
      options: {
        redirectTo: `${window.location.origin}/`,
      },
    });
    if (oauthError) setError(oauthError.message);
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
      style={{ background: "#0c0e10" }}
    >
      {/* Gradient backdrop */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `
            radial-gradient(ellipse 90% 70% at 40% 0%, rgba(59, 130, 246, 0.30) 0%, transparent 50%),
            radial-gradient(ellipse 70% 60% at 80% 20%, rgba(168, 85, 247, 0.22) 0%, transparent 50%),
            radial-gradient(ellipse 60% 50% at 50% 95%, rgba(236, 72, 153, 0.18) 0%, transparent 50%)
          `,
        }}
      />

      <div className="w-full max-w-[400px] relative z-10">
        {/* Logo + Brand */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 rounded-2xl overflow-hidden mb-4 shadow-lg shadow-[#3b82f6]/20">
            <img
              src="/blu-hands-logo.png.png"
              alt="Blu Hands"
              className="w-full h-full object-cover"
            />
          </div>
          <h1 className="text-2xl font-semibold text-white">Blu Hands</h1>
          <p className="text-sm text-[#666] mt-1">Code less, make more</p>
        </div>

        {/* Auth Card */}
        <div className="bg-[#111318]/80 backdrop-blur-xl border border-[#2a2d37] rounded-2xl p-6">
          <h2 className="text-lg font-medium text-white mb-1">
            {mode === "login" ? "Welcome back" : "Create an account"}
          </h2>
          <p className="text-sm text-[#666] mb-6">
            {mode === "login"
              ? "Sign in to continue building"
              : "Start building with Blu Hands"}
          </p>

          {/* OAuth Buttons */}
          <div className="flex flex-col gap-2.5 mb-5">
            <button
              type="button"
              onClick={handleGitHubLogin}
              className="w-full flex items-center justify-center gap-2.5 bg-[#1a1c22] border border-[#2a2d37] rounded-lg py-2.5 px-4 text-sm text-white hover:bg-[#1e2028] hover:border-[#3a3d47] transition-colors"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
              Continue with GitHub
            </button>
            <button
              type="button"
              onClick={handleGoogleLogin}
              className="w-full flex items-center justify-center gap-2.5 bg-[#1a1c22] border border-[#2a2d37] rounded-lg py-2.5 px-4 text-sm text-white hover:bg-[#1e2028] hover:border-[#3a3d47] transition-colors"
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Continue with Google
            </button>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-3 mb-5">
            <div className="flex-1 h-px bg-[#2a2d37]" />
            <span className="text-xs text-[#555]">or</span>
            <div className="flex-1 h-px bg-[#2a2d37]" />
          </div>

          {/* Email Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div>
              <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-[#1a1c22] border border-[#2a2d37] rounded-lg py-2.5 px-3.5 text-sm text-white placeholder-[#555] outline-none focus:border-[#3b82f6]/50 transition-colors"
              />
            </div>
            <div>
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full bg-[#1a1c22] border border-[#2a2d37] rounded-lg py-2.5 px-3.5 text-sm text-white placeholder-[#555] outline-none focus:border-[#3b82f6]/50 transition-colors"
              />
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg py-2 px-3">
                <p className="text-xs text-red-400">{error}</p>
              </div>
            )}

            {successMessage && (
              <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg py-2 px-3">
                <p className="text-xs text-emerald-400">{successMessage}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className={cn(
                "w-full rounded-lg py-2.5 px-4 text-sm font-medium transition-colors",
                "bg-[#3b82f6] text-white hover:bg-[#2563eb]",
                "disabled:opacity-50 disabled:cursor-not-allowed",
              )}
            >
              {loading
                ? "..."
                : mode === "login"
                  ? "Sign in"
                  : "Create account"}
            </button>
          </form>

          {/* Toggle mode */}
          <div className="mt-5 text-center">
            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "signup" : "login");
                setError(null);
                setSuccessMessage(null);
              }}
              className="text-xs text-[#9099ac] hover:text-white transition-colors"
            >
              {mode === "login"
                ? "Don't have an account? Sign up"
                : "Already have an account? Sign in"}
            </button>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-[11px] text-[#444] mt-6">
          Powered by Supabase Auth
        </p>
      </div>
    </div>
  );
}
