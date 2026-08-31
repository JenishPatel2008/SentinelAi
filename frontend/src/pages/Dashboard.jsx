import {
  AlertTriangle,
  Camera,
  Car,
  Eye,
  MapPin,
  ShieldCheck,
  Users,
} from "lucide-react";

import PageContainer from "../components/layout/PageContainer";
import Badge from "../components/ui/Badge";
import StatCard from "../components/ui/StatCard";

const stats = [
  {
    label: "Active Cameras",
    value: "24",
    detail: "24 / 24 online",
    icon: Camera,
  },
  {
    label: "Active Alerts",
    value: "03",
    detail: "2 high priority",
    icon: AlertTriangle,
  },
  {
    label: "People Detected",
    value: "18",
    detail: "Last 30 minutes",
    icon: Users,
  },
  {
    label: "Vehicles Detected",
    value: "07",
    detail: "Last 30 minutes",
    icon: Car,
  },
];

const cameras = [
  ["CAM-01", "North Perimeter", "Sector 01", "97%", 4],
  ["CAM-04", "East Ridge", "Sector 03", "94%", 2],
  ["CAM-07", "Restricted Zone", "Sector 04", "96%", 5],
  ["CAM-12", "South Checkpoint", "Sector 07", "91%", 1],
];

const alerts = [
  ["Border Intrusion", "CAM-07", "Sector 04", "16:42:13", "critical"],
  ["Restricted Zone Entry", "CAM-04", "Sector 03", "16:37:51", "high"],
  ["Vehicle Detected", "CAM-12", "Sector 07", "16:31:22", "medium"],
];

const events = [
  ["Person detected", "CAM-01", "16:45:02"],
  ["Vehicle detected", "CAM-12", "16:42:19"],
  ["Restricted zone monitored", "CAM-07", "16:38:44"],
  ["Person detected", "CAM-04", "16:35:17"],
];

function CameraCard({ camera }) {
  const [id, name, sector, confidence, detections] = camera;

  return (
    <div className="overflow-hidden rounded-xl border border-white/10 bg-[#0d1117]">
      <div className="relative aspect-video bg-[#151a22]">
        <div className="absolute inset-0 flex items-center justify-center">
          <Eye size={28} className="text-slate-700" />
        </div>

        <span className="absolute left-3 top-3 rounded bg-black/60 px-2 py-1 text-[10px] text-white">
          {id}
        </span>

        <span className="absolute right-3 top-3 flex items-center gap-1.5 rounded bg-black/60 px-2 py-1 text-[10px] text-slate-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          LIVE
        </span>

        <div className="absolute bottom-3 left-3 right-3 flex justify-between">
          <div>
            <p className="text-xs font-medium text-white">
              {name}
            </p>
            <p className="mt-1 text-[10px] text-slate-500">
              {sector}
            </p>
          </div>

          <span className="self-end rounded bg-black/60 px-2 py-1 text-[10px] text-slate-300">
            AI {confidence}
          </span>
        </div>
      </div>

      <div className="flex justify-between border-t border-white/5 px-4 py-3">
        <span className="text-[10px] text-slate-500">
          {detections} detections
        </span>

        <span className="text-[10px] text-emerald-400">
          Operational
        </span>
      </div>
    </div>
  );
}

export default function Dashboard() {
  return (
    <PageContainer>
      <div className="space-y-6">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-600">
              Monitoring Overview
            </p>

            <h1 className="mt-1 text-2xl font-semibold text-white">
              Border Surveillance
            </h1>

            <p className="mt-1 text-sm text-slate-500">
              Real-time intelligence across monitored sectors.
            </p>
          </div>

          <div className="hidden items-center gap-2 text-xs text-slate-500 md:flex">
            <MapPin size={14} />
            24 cameras across 8 sectors
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {stats.map((stat) => (
            <StatCard
              key={stat.label}
              {...stat}
            />
          ))}
        </div>

        <div className="grid gap-6 xl:grid-cols-[1fr_350px]">
          <section>
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-white">
                  Live Surveillance
                </h2>

                <p className="mt-1 text-[10px] text-slate-600">
                  AI-assisted camera monitoring
                </p>
              </div>

              <Badge variant="success">
                All Cameras Online
              </Badge>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {cameras.map((camera) => (
                <CameraCard
                  key={camera[0]}
                  camera={camera}
                />
              ))}
            </div>
          </section>

          <section className="rounded-xl border border-white/10 bg-[#0d1117]">
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <div>
                <h2 className="text-sm font-semibold text-white">
                  Critical Alerts
                </h2>

                <p className="mt-1 text-[10px] text-slate-600">
                  Requires operator attention
                </p>
              </div>

              <Badge variant="critical">03 Active</Badge>
            </div>

            <div className="divide-y divide-white/5">
              {alerts.map((alert) => (
                <div
                  key={`${alert[1]}-${alert[3]}`}
                  className="p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-xs font-medium text-slate-200">
                      {alert[0]}
                    </p>

                    <Badge variant={alert[4]}>
                      {alert[4]}
                    </Badge>
                  </div>

                  <p className="mt-2 text-[10px] text-slate-600">
                    {alert[1]} · {alert[2]}
                  </p>

                  <p className="mt-2 text-[10px] text-slate-500">
                    {alert[3]}
                  </p>
                </div>
              ))}
            </div>
          </section>
        </div>

        <section className="rounded-xl border border-white/10 bg-[#0d1117]">
          <div className="flex items-center gap-2 border-b border-white/10 px-5 py-4">
            <ShieldCheck
              size={16}
              className="text-emerald-400"
            />

            <h2 className="text-sm font-semibold text-white">
              Recent Events
            </h2>
          </div>

          <div className="divide-y divide-white/5">
            {events.map((event) => (
              <div
                key={`${event[1]}-${event[2]}`}
                className="flex items-center justify-between px-5 py-4"
              >
                <div>
                  <p className="text-xs text-slate-300">
                    {event[0]}
                  </p>

                  <p className="mt-1 text-[10px] text-slate-600">
                    {event[1]}
                  </p>
                </div>

                <span className="text-[10px] text-slate-600">
                  {event[2]}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </PageContainer>
  );
}