/**
 * Admin — user management table with search and role management.
 */
import React from "react";
import { forgeClient } from "#/api/bluhands-service/forge-axios";
import type { ForgeEnvelope } from "#/api/bluhands-service/forge.types";

interface UserRow {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  platform_role: string;
  created_at: string;
}

const ROLE_COLORS: Record<string, string> = {
  user: "#64748b",
  admin: "#f59e0b",
  tester: "#818cf8",
  self: "#34d399",
};

export default function AdminUsers() {
  const [users, setUsers] = React.useState<UserRow[]>([]);
  const [loading, setLoading] = React.useState(true);

  const fetchUsers = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await forgeClient.get<ForgeEnvelope<UserRow[]>>("/api/v1/admin/users");
      const payload = res.data?.data;
      setUsers(Array.isArray(payload) ? payload : []);
    } catch (e) {
      console.error(e);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const [busyId, setBusyId] = React.useState<string | null>(null);

  const changeRole = async (id: string, role: string) => {
    setBusyId(id);
    try {
      await forgeClient.patch(`/api/v1/admin/users/${id}/role`, {
        platform_role: role,
      });
      await fetchUsers();
    } catch (e) {
      console.error(e);
    } finally {
      setBusyId(null);
    }
  };

  const deleteUser = async (id: string, email: string) => {
    // eslint-disable-next-line no-alert
    if (!window.confirm(`Delete ${email}? This cannot be undone.`)) return;
    setBusyId(id);
    try {
      await forgeClient.delete(`/api/v1/admin/users/${id}`);
      await fetchUsers();
    } catch (e) {
      console.error(e);
    } finally {
      setBusyId(null);
    }
  };

  const ROLES = ["user", "admin", "tester", "self"];

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-white">Users</h1>

      <div className="overflow-hidden rounded-xl border border-[#1e293b]">
        <table className="w-full text-sm">
          <thead className="bg-[#0f1117] text-left text-xs uppercase tracking-wider text-[#475569]">
            <tr>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Active</th>
              <th className="px-4 py-3">Joined</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-[#475569]">
                  Loading…
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-[#475569]">
                  No users found
                </td>
              </tr>
            ) : (
              users.map((u, i) => (
                <tr
                  key={u.id}
                  className={`border-t border-[#1e293b] ${i % 2 === 0 ? "bg-[#111318]" : "bg-[#0f1117]"}`}
                >
                  <td className="px-4 py-3 text-white">{u.email}</td>
                  <td className="px-4 py-3 text-[#94a3b8]">
                    {u.full_name ?? <span className="text-[#475569]">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="rounded-full px-2 py-0.5 text-xs font-semibold"
                      style={{
                        color: ROLE_COLORS[u.platform_role] ?? "#94a3b8",
                        background: `${ROLE_COLORS[u.platform_role] ?? "#94a3b8"}22`,
                      }}
                    >
                      {u.platform_role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[#94a3b8]">
                    {u.is_active ? "✓" : "✗"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-[#475569]">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <select
                        value={u.platform_role}
                        disabled={busyId === u.id}
                        onChange={(e) => changeRole(u.id, e.target.value)}
                        className="rounded-md border border-[#2a2d37] bg-[#0f1117] px-2 py-1 text-xs text-white outline-none disabled:opacity-50"
                        aria-label="Change role"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        disabled={busyId === u.id}
                        onClick={() => deleteUser(u.id, u.email)}
                        className="rounded-md border border-[#2a2d37] px-2 py-1 text-xs text-[#94a3b8] transition-colors hover:border-red-500/40 hover:text-red-400 disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-[#475569]">Showing up to 100 results</p>
    </div>
  );
}
