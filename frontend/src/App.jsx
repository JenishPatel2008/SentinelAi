import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import Dashboard from "./pages/Dashboard";

function Placeholder({ title }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#090c11]">
      <h1 className="text-2xl font-semibold text-white">
        {title}
      </h1>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<Navigate to="/dashboard" replace />}
        />

        <Route
          path="/dashboard"
          element={<Dashboard />}
        />

        <Route
          path="/monitoring"
          element={<Placeholder title="Live Monitoring" />}
        />

        <Route
          path="/alerts"
          element={<Placeholder title="Alerts" />}
        />

        <Route
          path="/events"
          element={<Placeholder title="Events" />}
        />

        <Route
          path="/cameras"
          element={<Placeholder title="Cameras" />}
        />

        <Route
          path="/map"
          element={<Placeholder title="Border Map" />}
        />

        <Route
          path="/analytics"
          element={<Placeholder title="Analytics" />}
        />

        <Route
          path="/settings"
          element={<Placeholder title="Settings" />}
        />

        <Route
          path="/login"
          element={<Placeholder title="Login" />}
        />
      </Routes>
    </BrowserRouter>
  );
}