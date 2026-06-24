"use client";

/**
 * /admin — platform admin panel.
 *
 * Standalone client page: has its own Supabase login, then calls
 *   GET  /api/v1/admin/users
 *   PATCH /api/v1/admin/users/{id}/role
 * The user must already be platform_admin in the control-plane DB.
 */

import { useState } from "react";
import { Loader2, ShieldCheck } from "lucide-react";
import { supabase } from "@/lib/supabase";

const CONTROL_PLANE_URL =
  process.env.NEXT_PUBLIC_CONTROL_PLANE_URL ?? "http://localhost:8000";

const PLATFORM_ROLES = ["user", "admin", "tester", "self"] as const;
type PlatformRole = (typeof PLATFORM_ROLES)[number];

interface AdminUser {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  platform_role: PlatformRole;
  created_at: string;
}

async function apiFetch<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${CONTROL_PLANE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body?.error?.message ?? `Request failed (${res.status})`);
  return (body.data ?? body) as T;
}

// ---- Login form ----

function LoginForm({ onToken }: { onToken: (token: string) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { data, error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (signInError) throw new Error(signInError.message);
      if (!data.session?.access_token) throw new Error("No session returned.");
      onToken(data.session.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4 rounded-lg border border-border bg-card p-8">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <ShieldCheck className="h-5 w-5 text-primary" />
          Admin sign in
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Password</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          Sign in
        </button>
      </form>
    </div>
  );
}

// ---- User table row ----

function UserRow({
  user,
  token,
  onUpdated,
}: {
  user: AdminUser;
  token: string;
  onUpdated: (u: AdminUser) => void;
}) {
  const [busy, setBusy] = useState(false);

  const setRole = async (role: PlatformRole) => {
    if (role === user.platform_role) return;
    setBusy(true);
    try {
      const updated = await apiFetch<AdminUser>(
        `/api/v1/admin/users/${user.id}/role`,
        token,
        { method: "PATCH", body: JSON.stringify({ platform_role: role }) },
      );
      onUpdated(updated);
    } catch {
      // silently ignore — refresh will show real state
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className="border-t border-border text-sm">
      <td className="px-4 py-3">
        <p className="font-medium">{user.full_name ?? "—"}</p>
        <p className="text-muted-foreground">{user.email}</p>
      </td>
      <td className="px-4 py-3">
        <span className={`rounded px-2 py-0.5 text-xs font-medium ${user.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}>
          {user.is_active ? "active" : "inactive"}
        </span>
      </td>
      <td className="px-4 py-3">
        <select
          value={user.platform_role}
          disabled={busy}
          onChange={(e) => setRole(e.target.value as PlatformRole)}
          className="rounded-md border border-border bg-card px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
        >
          {PLATFORM_ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-3 text-muted-foreground">
        {new Date(user.created_at).toLocaleDateString()}
      </td>
    </tr>
  );
}

// ---- Main panel ----

function AdminPanel({ token }: { token: string }) {
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = () => {
    setError(null);
    apiFetch<AdminUser[]>("/api/v1/admin/users", token)
      .then((data) => {
        setUsers(data);
        setLoaded(true);
      })
      .catch((err) => setError(err.message));
  };

  // Load on first render
  if (!loaded && !error) {
    load();
  }

  const updateUser = (updated: AdminUser) =>
    setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? null);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-bold">Platform users</h1>
        </div>
        <button
          onClick={load}
          className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-700">
          {error}
          {error.includes("admin") && (
            <span> — make sure your account has platform_role = admin in the control-plane DB.</span>
          )}
        </div>
      )}

      {!users && !error && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading users…
        </div>
      )}

      {users && (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full">
            <thead className="bg-muted/50 text-left text-xs font-medium uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Platform role</th>
                <th className="px-4 py-3">Joined</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <UserRow key={u.id} user={u} token={token} onUpdated={updateUser} />
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-sm text-muted-foreground">
                    No users found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---- Page entry ----

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(null);

  if (!token) return <LoginForm onToken={setToken} />;
  return <AdminPanel token={token} />;
}
