import { NavLink, Route, Routes } from "react-router-dom";
import Backup from "./pages/Backup";
import Cleanup from "./pages/Cleanup";
import Dashboard from "./pages/Dashboard";
import Discover from "./pages/Discover";
import History from "./pages/History";
import Settings from "./pages/Settings";
import { DeviceProvider, useDevice } from "./state/device";

const NAV = [
  { to: "/", label: "Device", end: true },
  { to: "/discover", label: "Discover" },
  { to: "/backup", label: "Back Up" },
  { to: "/cleanup", label: "Cleanup" },
  { to: "/history", label: "History" },
  { to: "/settings", label: "Options" },
];

function AppIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" className="titlebar-icon" aria-hidden="true">
      <rect x="3" y="1" width="10" height="14" rx="1.5" fill="#0067c0" />
      <rect x="4.5" y="3" width="7" height="9" fill="#cce8ff" />
      <rect x="6.5" y="13" width="3" height="1" rx="0.5" fill="#cce8ff" />
    </svg>
  );
}

function StatusBar() {
  const { status, loading, error, refresh } = useDevice();
  const connected = !!status?.connected;
  const dev = status?.device;

  return (
    <div className="statusbar">
      <div className="statusbar-cell">
        <span className={"status-led " + (loading ? "" : connected ? "on" : "off")} />
        {loading ? "Checking device..." : connected ? "Device connected" : "No device"}
      </div>
      <div className="statusbar-cell grow">
        {error
          ? `Error: ${error}`
          : connected && dev
          ? `${dev.manufacturer} ${dev.model} — Android ${dev.android_version} (SDK ${dev.sdk})`
          : status?.reason || ""}
      </div>
      {connected && dev && (
        <div className="statusbar-cell optional">{dev.serial}</div>
      )}
      <div className="statusbar-cell right">
        <button className="link" onClick={refresh} disabled={loading}>Refresh</button>
      </div>
    </div>
  );
}

function Shell() {
  return (
    <div className="app-shell">
      <header className="titlebar">
        <AppIcon />
        <span>Android Backup Manager</span>
        <span className="titlebar-sep" />
        <span className="titlebar-meta">Local tool — 127.0.0.1</span>
      </header>

      <div className="app-body">
        <nav className="navpane" aria-label="Sections">
          <div className="navpane-group">Tasks</div>
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/discover" element={<Discover />} />
            <Route path="/backup" element={<Backup />} />
            <Route path="/cleanup" element={<Cleanup />} />
            <Route path="/history" element={<History />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>

      <StatusBar />
    </div>
  );
}

export default function App() {
  return (
    <DeviceProvider>
      <Shell />
    </DeviceProvider>
  );
}
