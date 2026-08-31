export default function StatCard({
  icon: Icon,
  label,
  value,
  detail,
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0d1117] p-5">
      <div className="flex items-start justify-between">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500/10 text-blue-400">
          <Icon size={18} />
        </div>

        <span className="h-2 w-2 rounded-full bg-emerald-400" />
      </div>

      <p className="mt-5 text-xs text-slate-500">
        {label}
      </p>

      <div className="mt-1 flex items-end gap-3">
        <span className="text-2xl font-semibold text-white">
          {value}
        </span>

        <span className="mb-1 text-[10px] text-slate-600">
          {detail}
        </span>
      </div>
    </div>
  );
}