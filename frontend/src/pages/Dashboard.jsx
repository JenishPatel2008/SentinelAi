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
import useCameras from "../hooks/useCameras";

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

const alerts = [
  {
    id: 1,
    title: "Border Intrusion",
    camera: "CAM-07",
    sector: "Sector 04",
    time: "16:42:13",
    severity: "critical",
  },
  {
    id: 2,
    title: "Restricted Zone Entry",
    camera: "CAM-04",
    sector: "Sector 03",
    time: "16:37:51",
    severity: "high",
  },
  {
    id: 3,
    title: "Vehicle Detected",
    camera: "CAM-12",
    sector: "Sector 07",
    time: "16:31:22",
    severity: "medium",
  },
];

const events = [
  {
    id: 1,
    event: "Person detected",
    camera: "CAM-01",
    time: "16:45:02",
  },
  {
    id: 2,
    event: "Vehicle detected",
    camera: "CAM-12",
    time: "16:42:19",
  },
  {
    id: 3,
    event: "Restricted zone monitored",
    camera: "CAM-07",
    time: "16:38:44",
  },
  {
    id: 4,
    event: "Person detected",
    camera: "CAM-04",
    time: "16:35:17",
  },
];

function CameraCard({ camera }) {
  return (
    <div className="overflow-hidden rounded-xl border border-white/10 bg-[#0d1117]">
      <div className="relative aspect-video bg-[#151a22]">
        <div className="absolute inset-0 flex items-center justify-center">
          <Eye
            size={30}
            className="text-slate-700"
          />
        </div>

        <div className="absolute left-3 top-3 rounded bg-black/60 px-2 py-1 text-[10px] font-medium text-white">
          {camera.camera_code}
        </div>

        <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded bg-black/60 px-2 py-1 text-[10px] font-medium text-slate-300">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              camera.is_active
                ? "bg-emerald-400"
                : "bg-red-400"
            }`}
          />

          {camera.is_active ? "LIVE" : "OFFLINE"}
        </div>

        <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between">
          <div>
            <p className="text-xs font-medium text-white">
              {camera.name}
            </p>

            <p className="mt-1 text-[10px] text-slate-500">
              {camera.sector}
            </p>
          </div>

          <span className="rounded bg-black/60 px-2 py-1 text-[10px] text-slate-400">
            AI READY
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between border-t border-white/5 px-4 py-3">
        <span className="text-[10px] text-slate-500">
          Camera ID: {camera.id}
        </span>

        <span
          className={`text-[10px] ${
            camera.is_active
              ? "text-emerald-400"
              : "text-red-400"
          }`}
        >
          {camera.is_active
            ? "Operational"
            : "Offline"}
        </span>
      </div>
    </div>
  );
}

function CameraGrid({
  cameras,
  loading,
  error,
}) {
  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        {[1, 2, 3, 4].map((item) => (
          <div
            key={item}
            className="aspect-video animate-pulse rounded-xl border border-white/10 bg-[#0d1117]"
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center">
        <AlertTriangle
          size={24}
          className="mx-auto text-red-400"
        />

        <p className="mt-3 text-sm text-red-400">
          Unable to load cameras
        </p>

        <p className="mt-1 text-xs text-slate-600">
          {error}
        </p>
      </div>
    );
  }

  if (cameras.length === 0) {
    return (
      <div className="rounded-xl border border-white/10 bg-[#0d1117] p-10 text-center">
        <Camera
          size={28}
          className="mx-auto text-slate-700"
        />

        <p className="mt-3 text-sm text-slate-400">
          No cameras registered
        </p>

        <p className="mt-1 text-xs text-slate-600">
          Add cameras from the Cameras section.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {cameras.map((camera) => (
        <CameraCard
          key={camera.id}
          camera={camera}
        />
      ))}
    </div>
  );
}

export default function Dashboard() {
  const {
    cameras,
    loading: camerasLoading,
    error: camerasError,
  } = useCameras();

  return (
    <PageContainer>
      <div className="space-y-6">

        {/* Page heading */}
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

            {cameras.length} registered cameras
          </div>
        </div>

        {/* Statistics */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {stats.map((stat) => (
            <StatCard
              key={stat.label}
              {...stat}
            />
          ))}
        </div>

        {/* Surveillance + Alerts */}
        <div className="grid gap-6 xl:grid-cols-[1fr_350px]">

          {/* Camera section */}
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
                {cameras.length} Cameras
              </Badge>
            </div>

            <CameraGrid
              cameras={cameras}
              loading={camerasLoading}
              error={camerasError}
            />
          </section>

          {/* Alerts */}
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

              <Badge variant="critical">
                {alerts.length} Active
              </Badge>
            </div>

            <div className="divide-y divide-white/5">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className="p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-xs font-medium text-slate-200">
                      {alert.title}
                    </p>

                    <Badge variant={alert.severity}>
                      {alert.severity}
                    </Badge>
                  </div>

                  <p className="mt-2 text-[10px] text-slate-600">
                    {alert.camera} · {alert.sector}
                  </p>

                  <p className="mt-2 text-[10px] text-slate-500">
                    {alert.time}
                  </p>
                </div>
              ))}
            </div>

          </section>
        </div>

        {/* Recent events */}
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
                key={event.id}
                className="flex items-center justify-between px-5 py-4"
              >
                <div>
                  <p className="text-xs text-slate-300">
                    {event.event}
                  </p>

                  <p className="mt-1 text-[10px] text-slate-600">
                    {event.camera}
                  </p>
                </div>

                <span className="text-[10px] text-slate-600">
                  {event.time}
                </span>
              </div>
            ))}
          </div>

        </section>

      </div>
    </PageContainer>
  );
}