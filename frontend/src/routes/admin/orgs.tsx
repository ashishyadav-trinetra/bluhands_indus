/**
 * Admin — organisation listing table.
 */
import React from "react";
import { forgeClient } from "#/api/bluhands-service/forge-axios";
import type { ForgeEnvelope } from "#/api/bluhands-service/forge.types";

interface OrgRow {
  id: string;
  name: string;
  created_at: string;
}

export default function AdminOrgs() {
  const [orgs, setOrgs] = React.useState<OrgRow[]>([]);
  const [loading, setLoading] = React.useState(true);

  const fetchOrgs = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await forgeClient.get<ForgeEnvelope<OrgRow[]>>("/api/v1/admin/orgs");
      const payload = res.data?.data;
      setOrgs(Array.isArray(payload) ? payload : []);
    } catch (e) {
      console.error(e);
      setOrgs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchOrgs();
  }, [fetchOrgs]);

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-white">Organisations</h1>

      <div className="overflow-hidden rounded-xl border border-[#1e293b]">
        <table className="w-full text-sm">
          <thead className="bg-[#0f1117] text-left text-xs uppercase tracking-wider text-[#475569]">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Created</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={2} className="py-12 text-center text-[#475569]">
                  Loading…
                </td>
              </tr>
            ) : orgs.length === 0 ? (
              <tr>
                <td colSpan={2} className="py-12 text-center text-[#475569]">
                  No organisations found
                </td>
              </tr>
            ) : (
              orgs.map((org, i) => (
                <tr
                  key={org.id}
                  className={`border-t border-[#1e293b] ${i % 2 === 0 ? "bg-[#111318]" : "bg-[#0f1117]"}`}
                >
                  <td className="px-4 py-3 text-white">{org.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-[#475569]">
                    {new Date(org.created_at).toLocaleDateString()}
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
