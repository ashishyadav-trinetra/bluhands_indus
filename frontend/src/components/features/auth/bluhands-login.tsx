/* eslint-disable i18next/no-literal-string */
import React from "react";
import { useNavigate } from "react-router";
import {
  AuthError,
  googleLoginEnabled,
  login,
  register,
  restoreSession,
  startGoogleLogin,
} from "#/lib/auth";
import { cn } from "#/utils/utils";
import { queryClient } from "#/query-client-config";

type AuthMode = "login" | "signup";

const INPUT_CLASS =
  "w-full bg-[#1a1c22] border border-[#2a2d37] rounded-lg py-2.5 px-3.5 text-sm text-white placeholder-[#555] outline-none focus:border-[#3b82f6]/50 transition-colors";

export function BluHandsLogin() {
  const navigate = useNavigate();
  const [mode, setMode] = React.useState<AuthMode>("login");

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [fullName, setFullName] = React.useState("");
  const [organizationName, setOrganizationName] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  // If the refresh cookie is still valid, skip the form entirely. Covers both a
  // returning visitor and the redirect back from a successful Google sign-in.
  React.useEffect(() => {
    let cancelled = false;
    restoreSession().then((authed) => {
      if (authed && !cancelled) navigate("/", { replace: true });
    });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  // The OAuth callback bounces here with ?error=oauth when Google sign-in fails
  // or the user cancels at the consent screen.
  React.useEffect(() => {
    if (new URLSearchParams(window.location.search).get("error") === "oauth") {
      setError("Google sign-in did not complete. Please try again.");
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "signup") {
        await register({
          email,
          password,
          organizationName,
          fullName: fullName.trim() || undefined,
        });
      } else {
        await login(email, password);
      }
      queryClient.clear();
      navigate("/", { replace: true });
    } catch (err: unknown) {
      setError(
        err instanceof AuthError
          ? err.message
          : "Could not reach the server. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setMode(mode === "login" ? "signup" : "login");
    setError(null);
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

          {googleLoginEnabled && (
            <>
              <button
                type="button"
                onClick={startGoogleLogin}
                className="w-full flex items-center justify-center gap-2.5 bg-[#1a1c22] border border-[#2a2d37] rounded-lg py-2.5 px-4 text-sm text-white hover:bg-[#1e2028] hover:border-[#3a3d47] transition-colors mb-5"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
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

              <div className="flex items-center gap-3 mb-5">
                <div className="flex-1 h-px bg-[#2a2d37]" />
                <span className="text-xs text-[#555]">or</span>
                <div className="flex-1 h-px bg-[#2a2d37]" />
              </div>
            </>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className={INPUT_CLASS}
            />

            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete={
                mode === "signup" ? "new-password" : "current-password"
              }
              className={INPUT_CLASS}
            />

            {mode === "signup" && (
              <>
                <input
                  type="text"
                  placeholder="Your name (optional)"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  maxLength={200}
                  autoComplete="name"
                  className={INPUT_CLASS}
                />
                <input
                  type="text"
                  placeholder="Workspace name"
                  value={organizationName}
                  onChange={(e) => setOrganizationName(e.target.value)}
                  required
                  maxLength={200}
                  autoComplete="organization"
                  className={INPUT_CLASS}
                />
                <p className="text-[11px] text-[#555] -mt-1">
                  Passwords must be at least 8 characters.
                </p>
              </>
            )}

            {error && (
              <div
                role="alert"
                className="bg-red-500/10 border border-red-500/20 rounded-lg py-2 px-3"
              >
                <p className="text-xs text-red-400">{error}</p>
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
              {loading && "..."}
              {!loading && mode === "login" && "Sign in"}
              {!loading && mode === "signup" && "Create account"}
            </button>
          </form>

          {/* Toggle mode */}
          <div className="mt-5 text-center">
            <button
              type="button"
              onClick={switchMode}
              className="text-xs text-[#9099ac] hover:text-white transition-colors"
            >
              {mode === "login"
                ? "Don't have an account? Sign up"
                : "Already have an account? Sign in"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
