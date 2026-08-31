import Header from "./Header";
import Sidebar from "./Sidebar";

export default function PageContainer({ children }) {
  return (
    <div className="min-h-screen bg-[#090c11] text-slate-200">
      <Sidebar />

      <div className="ml-64 min-h-screen">
        <Header />

        <main className="p-7">
          {children}
        </main>
      </div>
    </div>
  );
}