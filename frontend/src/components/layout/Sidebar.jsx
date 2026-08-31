import {
  Activity,
  BarChart3,
  Bell,
  Camera,
  ClipboardList,
  LayoutDashboard,
  Map,
  Settings,
  Shield,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const navigation = [
  { name: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
  { name: "Live Monitoring", path: "/monitoring", icon: Activity },
  { name: "Alerts", path: "/alerts", icon: Bell },
  { name: "Events", path: "/events", icon: ClipboardList },
  { name: "Cameras", path: "/cameras", icon: Camera },
  { name: "Border Map", path: "/map", icon: Map },
  { name: "Analytics", path: "/analytics", icon: BarChart3 },
  { name: "Settings", path: "/settings", icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-white/10 bg-[#0b0f14]">
      <div className="flex h-20 items-center gap-3 border-b border-white/10 px-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400">
          <Shield size={21} />
        </div>

        <div>
          <h1 className="text-sm font-bold tracking-wider text-white">
            SENTINEL AI
          </h1>

          <p className="mt-0.5 text-[9px] uppercase tracking-[0.2em] text-slate-500">
            Border Control Unit
          </p>
        </div>
      </div>

      <nav className="flex-1 px-3 py-5">
        <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
          Operations
        </p>

        <div className="space-y-1">
          {navigation.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                    isActive
                      ? "bg-blue-500/10 text-blue-400"
                      : "text-slate-400 hover:bg-white/5 hover:text-white"
                  }`
                }
              >
                <Icon size={17} />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </div>
      </nav>

      <div className="border-t border-white/10 p-4">
        <div className="rounded-lg bg-white/[0.03] p-3">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />

            <span className="text-xs font-medium text-emerald-400">
              System Operational
            </span>
          </div>

          <p className="mt-2 text-[10px] text-slate-600">
            All surveillance systems online
          </p>
        </div>
      </div>
    </aside>
  );
}