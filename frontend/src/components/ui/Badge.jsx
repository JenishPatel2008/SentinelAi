const styles = {
  critical: "border-red-500/20 bg-red-500/10 text-red-400",
  high: "border-orange-500/20 bg-orange-500/10 text-orange-400",
  medium: "border-yellow-500/20 bg-yellow-500/10 text-yellow-400",
  low: "border-blue-500/20 bg-blue-500/10 text-blue-400",
  success: "border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
  neutral: "border-white/10 bg-white/5 text-slate-400",
};

export default function Badge({
  children,
  variant = "neutral",
}) {
  return (
    <span
      className={`inline-flex rounded-md border px-2 py-1 text-[10px] font-medium uppercase tracking-wide ${styles[variant]}`}
    >
      {children}
    </span>
  );
}