/**
 * Native BluHands auth — replaces Supabase Auth.
 *
 * Design: the short-lived access token lives in memory only (never
 * localStorage, so an XSS cannot read it). The refresh token is an HttpOnly
 * cookie the browser sends automatically to /auth/refresh — JS never sees it.
 * On boot, and whenever the access token expires, we silently exchange the
 * cookie for a new access token.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8080";
const AUTH = `${API_BASE}/api/v1/auth`;

// Refresh this many ms before actual expiry, so in-flight requests don't race it.
const REFRESH_SKEW_MS = 30_000;

let accessToken: string | null = null;
let expiresAt = 0;
let refreshInFlight: Promise<string | null> | null = null;

type Listener = (authed: boolean) => void;
const listeners = new Set<Listener>();

function notify(): void {
  const authed = accessToken !== null;
  listeners.forEach((fn) => fn(authed));
}

/** Subscribe to sign-in/sign-out. Returns an unsubscribe function. */
export function onAuthChange(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function setSession(token: string, expiresIn: number): void {
  accessToken = token;
  expiresAt = Date.now() + expiresIn * 1000;
  notify();
}

function clearSession(): void {
  accessToken = null;
  expiresAt = 0;
  notify();
}

/** Error carrying the server's message so the UI can show something useful. */
export class AuthError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "AuthError";
    this.status = status;
  }
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${AUTH}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // Required for the HttpOnly refresh cookie to be sent and set.
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const payload = await response.json();
      message = payload?.error?.message || payload?.detail || message;
    } catch {
      // Non-JSON error body — keep the generic message.
    }
    if (response.status === 429) {
      message = "Too many attempts. Please wait a moment and try again.";
    }
    throw new AuthError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  const payload = await response.json();
  return payload.data as T;
}

interface TokenResponse {
  access_token: string;
  expires_in: number;
}

export interface RegisterInput {
  email: string;
  password: string;
  organizationName: string;
  fullName?: string;
}

/** Create a user + their first organization, and sign them in. */
export async function register(input: RegisterInput): Promise<void> {
  const tokens = await post<TokenResponse>("/register", {
    email: input.email,
    password: input.password,
    full_name: input.fullName || null,
    organization_name: input.organizationName,
  });
  setSession(tokens.access_token, tokens.expires_in);
}

export async function login(email: string, password: string): Promise<void> {
  const tokens = await post<TokenResponse>("/login", { email, password });
  setSession(tokens.access_token, tokens.expires_in);
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${AUTH}/logout`, {
      method: "POST",
      credentials: "include",
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });
  } catch {
    // Network failure shouldn't trap the user in a signed-in UI.
  }
  clearSession();
}

/**
 * Exchange the refresh cookie for a fresh access token.
 * Concurrent callers share one in-flight request.
 */
export function refresh(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = post<TokenResponse>("/refresh")
    .then((tokens) => {
      setSession(tokens.access_token, tokens.expires_in);
      return tokens.access_token;
    })
    .catch(() => {
      // No cookie, expired, or already rotated — treat as signed out.
      clearSession();
      return null;
    })
    .finally(() => {
      refreshInFlight = null;
    });

  return refreshInFlight;
}

/**
 * The current access token, refreshing first if it's missing or about to
 * expire. Returns null when the user is not signed in.
 */
export async function getAccessToken(): Promise<string | null> {
  if (accessToken && Date.now() < expiresAt - REFRESH_SKEW_MS) {
    return accessToken;
  }
  return refresh();
}

/** True if a session could be restored. Call once on app boot. */
export async function restoreSession(): Promise<boolean> {
  return (await refresh()) !== null;
}

/** Synchronous check for render-time guards. Prefer restoreSession on boot. */
export function isAuthenticated(): boolean {
  return accessToken !== null;
}

/**
 * Hand the browser to the control-plane, which redirects on to Google.
 * A full navigation (not fetch) — the OAuth dance needs real redirects.
 */
export function startGoogleLogin(): void {
  window.location.href = `${AUTH}/oauth/google/start`;
}

/** True when this deployment has Google sign-in configured. */
export const googleLoginEnabled =
  import.meta.env.VITE_GOOGLE_LOGIN_ENABLED === "true";

/** Extract the user's email directly from the in-memory access token JWT payload. */
export function getUserEmailFromToken(): string | null {
  if (!accessToken) return null;
  try {
    const base64Url = accessToken.split(".")[1];
    if (!base64Url) return null;
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => `%${`00${c.charCodeAt(0).toString(16)}`.slice(-2)}`)
        .join(""),
    );
    const payload = JSON.parse(jsonPayload);
    return payload.email || payload.user_metadata?.email || null;
  } catch {
    return null;
  }
}
