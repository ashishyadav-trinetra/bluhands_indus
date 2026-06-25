/**
 * Admin dashboard — platform-wide metrics.
 */
import React from "react";
import { forgeClient } from "#/api/bluhands-service/forge-axios";

interface Stats {
  total_users: number;
  total_orgs: number;
  paid_orgs: number;
  free_orgs: number;
  pro_orgs: number;
  business_orgs: number;
}

function StatCard({
  label,
  value,
  sub,
  color = "#7C3AED",
}: {
  label: string;
  value: number | string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="rounded-2xl border border-[#1e293b] bg-[#111318] p-6">
      <p className="text-sm text-[#64748b]">{label}</p>
      <p className="mt-2 text-4xl font-bold" style={{ color }}>
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-[#475569]">{sub}</p>}
    </div>
  );
}

export default function AdminDashboard() {
  const [stats, setStats] = React.useState<Stats | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    forgeClient
      .get<{ data: Stats }>("/admin/stats")
      .then((r) => setStats(r.data.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#7C3AED]" />
      </div>
    );
  }

  if (!stats) return <p className="text-[#64748b]">Failed to load stats.</p>;

  const paidPct =
    stats.total_orgs > 0
      ? Math.round((stats.paid_orgs / stats.total_orgs) * 100)
      : 0;

  return (
    <div>
      <h1 className="mb-8 text-2xl font-bold text-white">Dashboard</h1>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Total users"
          value={stats.total_users}
          color="#a78bfa"
        />
        <StatCard label="Total orgs" value={stats.total_orgs} color="#60a5fa" />
        <StatCard
          label="Paid orgs"
          value={stats.paid_orgs}
          sub={`${paidPct}% of all orgs`}
          color="#34d399"
        />
        <StatCard label="Free orgs" value={stats.free_orgs} color="#94a3b8" />
      </div>

      <div className="mt-8 grid grid-cols-2 gap-4">
        <StatCard
          label="Pro subscribers"
          value={stats.pro_orgs}
          color="#818cf8"
        />
        <StatCard
          label="Business subscribers"
          value={stats.business_orgs}
          color="#f59e0b"
        />
      </div>

      {/* Quick links */}
      <div className="mt-10">
        <h2 className="mb-4 text-lg font-semibold text-white">Quick actions</h2>
        <div className="flex gap-3">
          <a
            href="/admin/users"
            className="rounded-lg border border-[#1e293b] bg-[#111318] px-4 py-2 text-sm text-[#94a3b8] hover:border-[#7C3AED] hover:text-white"
          >
            → Manage users
          </a>
          <a
            href="/admin/orgs"
            className="rounded-lg border border-[#1e293b] bg-[#111318] px-4 py-2 text-sm text-[#94a3b8] hover:border-[#7C3AED] hover:text-white"
          >
            → Manage orgs
          </a>
        </div>
      </div>
    </div>
  );
}
