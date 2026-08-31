import PageContainer from "C:\\Users\\jenis_g\\Desktop\\AIT\\Sem 1\\Events\\Hackathons\\SIH\\Sentinel Ai\\frontend\\src\\components\\layout\\PageContainer.jsx";

const events = [
  {
    id: 1,
    event: "Person detected",
    camera: "CAM-01",
    sector: "Sector 01",
    time: "16:45:02",
  },
  {
    id: 2,
    event: "Vehicle detected",
    camera: "CAM-12",
    sector: "Sector 07",
    time: "16:42:19",
  },
  {
    id: 3,
    event: "Restricted zone monitored",
    camera: "CAM-07",
    sector: "Sector 04",
    time: "16:38:44",
  },
  {
    id: 4,
    event: "Person detected",
    camera: "CAM-04",
    sector: "Sector 03",
    time: "16:35:17",
  },
];

export default function Events() {
  return (
    <PageContainer>
      <div className="space-y-6">
        <div>
          <p className="text-[10px] uppercase tracking-[0.2em] text-slate-600">
            Surveillance History
          </p>

          <h1 className="mt-1 text-2xl font-semibold text-white">
            Events
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            Recorded events across monitored border sectors.
          </p>
        </div>

        <div className="overflow-hidden rounded-xl border border-white/10 bg-[#0d1117]">
          <div className="grid grid-cols-[1fr_120px_120px_120px] border-b border-white/10 px-5 py-3 text-[10px] uppercase tracking-wider text-slate-600">
            <span>Event</span>
            <span>Camera</span>
            <span>Sector</span>
            <span>Time</span>
          </div>

          <div className="divide-y divide-white/5">
            {events.map((event) => (
              <div
                key={event.id}
                className="grid grid-cols-[1fr_120px_120px_120px] items-center px-5 py-4"
              >
                <span className="text-xs text-slate-300">
                  {event.event}
                </span>

                <span className="text-xs text-slate-500">
                  {event.camera}
                </span>

                <span className="text-xs text-slate-500">
                  {event.sector}
                </span>

                <span className="text-xs text-slate-600">
                  {event.time}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </PageContainer>
  );
}