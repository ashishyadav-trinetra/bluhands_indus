import React from "react";
import { openHands } from "#/api/open-hands-axios";

interface Assignment {
  user_id: string;
  email: string;
  model: string;
  base_url: string;
  api_key: string;
  github_token: string;
  assigned_repo: string;
  is_active: boolean;
}

interface AssignmentForm {
  email: string;
  model: string;
  base_url: string;
  api_key: string;
  assigned_repo: string;
  is_active: boolean;
}

const EMPTY_FORM: AssignmentForm = {
  email: "",
  model: "",
  base_url: "",
  api_key: "",
  assigned_repo: "",
  is_active: true,
};

export default function AdminAssignments() {
  const [assignments, setAssignments] = React.useState<Assignment[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [form, setForm] = React.useState<AssignmentForm>(EMPTY_FORM);
  const [saving, setSaving] = React.useState(false);

  const fetchAssignments = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await openHands.get<Assignment[]>("/api/v1/admin/assignments");
      setAssignments(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      console.error(e);
      setError("Failed to load assignments");
      setAssignments([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchAssignments();
  }, [fetchAssignments]);

  const startEdit = (a: Assignment) => {
    setEditingId(a.user_id);
    setForm({
      email: a.email || "",
      model: a.model || "",
      base_url: a.base_url || "",
      api_key: "",
      assigned_repo: a.assigned_repo || "",
      is_active: a.is_active,
    });
  };

  const startAdd = () => {
    setEditingId("__new__");
    setForm(EMPTY_FORM);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
  };

  const saveAssignment = async () => {
    if (!form.model) return;
    setSaving(true);
    try {
      if (editingId === "__new__") {
        await openHands.put("/api/v1/admin/assignments/__new__", form);
      } else {
        await openHands.put(`/api/v1/admin/assignments/${editingId}`, form);
      }
      setEditingId(null);
      setForm(EMPTY_FORM);
      await fetchAssignments();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const deleteAssignment = async (userId: string, email: string) => {
    if (!window.confirm(`Remove assignment for ${email || userId}?`)) return;
    try {
      await openHands.delete(`/api/v1/admin/assignments/${userId}`);
      await fetchAssignments();
    } catch (e) {
      console.error(e);
    }
  };

  const toggleActive = async (a: Assignment) => {
    try {
      await openHands.put(`/api/v1/admin/assignments/${a.user_id}`, {
        email: a.email,
        model: a.model,
        base_url: a.base_url,
        api_key: "",
        assigned_repo: a.assigned_repo,
        is_active: !a.is_active,
      });
      await fetchAssignments();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Assignments</h1>
        <button
          type="button"
          onClick={startAdd}
          disabled={editingId !== null}
          className="rounded-lg bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#6D28D9] disabled:opacity-50"
        >
          + New assignment
        </button>
      </div>

      {error && (
        <p className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</p>
      )}

      {editingId !== null && (
        <div className="mb-6 rounded-xl border border-[#1e293b] bg-[#111318] p-4">
          <h2 className="mb-4 text-sm font-semibold text-white">
            {editingId === "__new__" ? "New assignment" : `Edit ${editingId}`}
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs text-[#64748b]">Email</label>
              <input
                type="text"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="w-full rounded-md border border-[#2a2d37] bg-[#0f1117] px-3 py-2 text-sm text-white outline-none"
                placeholder="user@example.com"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-[#64748b]">
                Model <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={form.model}
                onChange={(e) => setForm({ ...form, model: e.target.value })}
                className="w-full rounded-md border border-[#2a2d37] bg-[#0f1117] px-3 py-2 text-sm text-white outline-none"
                placeholder="openai/qwen3.6-35b-a3b"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-[#64748b]">Base URL</label>
              <input
                type="text"
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                className="w-full rounded-md border border-[#2a2d37] bg-[#0f1117] px-3 py-2 text-sm text-white outline-none"
                placeholder="https://api.bluehands.ai/v1"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-[#64748b]">API key</label>
              <input
                type="password"
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                className="w-full rounded-md border border-[#2a2d37] bg-[#0f1117] px-3 py-2 text-sm text-white outline-none"
                placeholder={editingId !== "__new__" ? "(leave blank to keep existing)" : ""}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-[#64748b]">Assigned repo</label>
              <input
                type="text"
                value={form.assigned_repo}
                onChange={(e) => setForm({ ...form, assigned_repo: e.target.value })}
                className="w-full rounded-md border border-[#2a2d37] bg-[#0f1117] px-3 py-2 text-sm text-white outline-none"
                placeholder="org/repo (optional)"
              />
            </div>
            <div className="flex items-end gap-3">
              <label className="flex items-center gap-2 text-sm text-[#94a3b8]">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  className="rounded border-[#2a2d37] bg-[#0f1117]"
                />
                Active
              </label>
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={saveAssignment}
              disabled={saving || !form.model}
              className="rounded-lg bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#6D28D9] disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              onClick={cancelEdit}
              className="rounded-lg border border-[#2a2d37] px-4 py-2 text-sm text-[#94a3b8] transition-colors hover:text-white"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-[#1e293b]">
        <table className="w-full text-sm">
          <thead className="bg-[#0f1117] text-left text-xs uppercase tracking-wider text-[#475569]">
            <tr>
              <th className="px-4 py-3">User ID</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Model</th>
              <th className="px-4 py-3">Base URL</th>
              <th className="px-4 py-3">Repo</th>
              <th className="px-4 py-3">Active</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-[#475569]">
                  Loading…
                </td>
              </tr>
            ) : assignments.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-[#475569]">
                  No assignments yet
                </td>
              </tr>
            ) : (
              assignments.map((a, i) => (
                <tr
                  key={a.user_id}
                  className={`border-t border-[#1e293b] ${i % 2 === 0 ? "bg-[#111318]" : "bg-[#0f1117]"}`}
                >
                  <td className="max-w-[180px] truncate px-4 py-3 font-mono text-xs text-white">
                    {a.user_id}
                  </td>
                  <td className="px-4 py-3 text-[#94a3b8]">{a.email || <span className="text-[#475569]">—</span>}</td>
                  <td className="px-4 py-3 font-mono text-xs text-[#a78bfa]">{a.model}</td>
                  <td className="max-w-[200px] truncate px-4 py-3 font-mono text-xs text-[#64748b]">
                    {a.base_url || <span className="text-[#475569]">—</span>}
                  </td>
                  <td className="px-4 py-3 text-[#94a3b8]">
                    {a.assigned_repo || <span className="text-[#475569]">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => toggleActive(a)}
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                        a.is_active
                          ? "bg-green-500/20 text-green-400"
                          : "bg-[#475569]/20 text-[#64748b]"
                      }`}
                    >
                      {a.is_active ? "Active" : "Inactive"}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => startEdit(a)}
                        className="rounded-md border border-[#2a2d37] px-2 py-1 text-xs text-[#94a3b8] transition-colors hover:text-white"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteAssignment(a.user_id, a.email)}
                        className="rounded-md border border-[#2a2d37] px-2 py-1 text-xs text-[#94a3b8] transition-colors hover:border-red-500/40 hover:text-red-400"
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
      <p className="mt-3 text-xs text-[#475569]">
        Assignments pin a user's model, base URL, and API key. The affected settings are locked
        in the user's LLM settings page.
      </p>
    </div>
  );
}
