import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

function PlaceholderPage({ title }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#090b10] text-white">
      <div className="text-center">
        <p className="mb-2 text-sm tracking-[0.25em] text-slate-500">
          SENTINEL AI
        </p>

        <h1 className="text-3xl font-semibold">
          {title}
        </h1>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<Navigate to="/dashboard" replace />}
        />

        <Route
          path="/dashboard"
          element={<PlaceholderPage title="Dashboard" />}
        />

        <Route
          path="/monitoring"
          element={<PlaceholderPage title="Live Monitoring" />}
        />

        <Route
          path="/alerts"
          element={<PlaceholderPage title="Alerts" />}
        />

        <Route
          path="/events"
          element={<PlaceholderPage title="Events" />}
        />

        <Route
          path="/cameras"
          element={<PlaceholderPage title="Cameras" />}
        />

        <Route
          path="/map"
          element={<PlaceholderPage title="Border Map" />}
        />

        <Route
          path="/analytics"
          element={<PlaceholderPage title="Analytics" />}
        />

        <Route
          path="/settings"
          element={<PlaceholderPage title="Settings" />}
        />

        <Route
          path="/login"
          element={<PlaceholderPage title="Login" />}
        />

        <Route
          path="*"
          element={<PlaceholderPage title="Page Not Found" />}
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;