import { Bell, ChevronDown } from "lucide-react";

export default function Header() {
  return (
    <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-white/10 bg-[#090c11]/95 px-7 backdrop-blur">
      <div>
        <p className="text-[10px] uppercase tracking-[0.2em] text-slate-600">
          Surveillance Command
        </p>

        <h2 className="mt-1 text-lg font-semibold text-white">
          Command Center
        </h2>
      </div>

      <div className="flex items-center gap-4">
        <button className="relative rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white">
          <Bell size={18} />

          <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-red-400" />
        </button>

        <div className="h-7 w-px bg-white/10" />

        <button className="flex items-center gap-2 rounded-lg p-1.5 hover:bg-white/5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-700 text-xs font-semibold text-white">
            OP
          </div>

          <div className="hidden text-left md:block">
            <p className="text-xs font-medium text-white">Operator</p>
            <p className="text-[10px] text-slate-600">Control Room</p>
          </div>

          <ChevronDown size={14} className="text-slate-500" />
        </button>
      </div>
    </header>
  );
}