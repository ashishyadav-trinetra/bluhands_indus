/**
 * Admin panel layout — sidebar navigation + super_admin gate.
 * Non-admins are redirected to home.
 */
import React from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router";
import { forgeClient } from "#/api/bluhands-service/forge-axios";

const NAV = [
  { label: "Dashboard", path: "/admin", icon: "📊" },
  { label: "Users", path: "/admin/users", icon: "👤" },
  { label: "Organisations", path: "/admin/orgs", icon: "🏢" },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [checking, setChecking] = React.useState(true);
  const [authorized, setAuthorized] = React.useState(false);

  // Gate check — hits /api/admin/stats; returns 403 for non-admins
  React.useEffect(() => {
    forgeClient
      .get("/admin/users")
      .then(() => {
        setAuthorized(true);
        setChecking(false);
      })
      .catch((err) => {
        if (err?.response?.status === 403 || err?.response?.status === 401) {
          navigate("/", { replace: true });
        }
        setChecking(false);
      });
  }, [navigate]);

  if (checking) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0c0e10]">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#7C3AED]" />
      </div>
    );
  }

  if (!authorized) return null;

  return (
    <div className="flex h-screen bg-[#0c0e10] text-white">
      {/* Sidebar */}
      <aside className="flex w-56 shrink-0 flex-col border-r border-[#1e293b] bg-[#0f1117] px-3 py-6">
        <div className="mb-8 px-2">
          <p className="text-xs font-semibold uppercase tracking-widest text-[#7C3AED]">
            Admin Panel
          </p>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map((item) => {
            const active =
              item.path === "/admin"
                ? location.pathname === "/admin"
                : location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`
                  flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors
                  ${active ? "bg-[#1e1040] text-[#a78bfa]" : "text-[#64748b] hover:bg-[#1e293b] hover:text-white"}
                `}
              >
                <span>{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto">
          <Link
            to="/"
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-[#475569] hover:text-white"
          >
            ← Back to app
          </Link>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
