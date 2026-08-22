import { NavLink, Route, Routes } from "react-router-dom";
import UpdateBanner from "./components/UpdateBanner";
import WorkflowRail from "./components/WorkflowRail";
import Backup from "./pages/Backup";
import Cleanup from "./pages/Cleanup";
import Dashboard from "./pages/Dashboard";
import Discover from "./pages/Discover";
import History from "./pages/History";
import Settings from "./pages/Settings";
import { DeviceProvider, useDevice } from "./state/device";
import { UpdateProvider } from "./state/update";

function AppIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 16 16" className="titlebar-icon" aria-hidden="true">
      <rect x="3" y="1" width="10" height="14" rx="1.6" fill="#2F81F7" />
      <rect x="4.5" y="3" width="7" height="9" fill="#0A0E14" />
      <rect x="6.4" y="13" width="3.2" height="1" rx="0.5" fill="#0A0E14" />
    </svg>
  );
}

/**
 * Live device state, kept in the top bar rather than only on the Device
 * page. Whether the phone is actually attached is the fact that decides
 * whether anything on any page will work, so it should never be more than
 * a glance away.
 */
function DeviceChip() {
  const { status, adb, loading } = useDevice();
  const connected = !!status?.connected;
  const device = status?.device;
  const adbMissing = adb ? !adb.found : false;

  const label = loading
    ? "Checking..."
    : adbMissing
    ? "Setup required"
    : connected && device
    ? `${device.manufacturer} ${device.model}`
    : "No device";

  return (
    <span className={"device-chip" + (connected ? " on" : "")}>
      <span className={"status-led " + (loading ? "" : connected ? "on" : "off")} />
      <span className="who">{label}</span>
    </span>
  );
}

function StatusBar() {
  const { status, adb, loading, error, refresh } = useDevice();
  const connected = !!status?.connected;
  const device = status?.device;
  const adbMissing = adb ? !adb.found : false;

  // A multi-line install hint truncated into a 30px bar helps nobody. When
  // adb is missing the bar states the fact and points at the page that can
  // actually fix it.
  const detail = error
    ? `Error: ${error}`
    : adbMissing
    ? "Android Platform Tools not installed — open Connect to set this up"
    : connected && device
    ? `Android ${device.android_version} (SDK ${device.sdk})`
    : status?.reason || "";

  return (
    <div className="statusbar">
      <div className="statusbar-cell">
        <span className={"status-led " + (loading ? "" : connected ? "on" : "off")} />
        {loading ? "Checking..." : adbMissing ? "Setup required" : connected ? "Connected" : "No device"}
      </div>
      <div className="statusbar-cell grow">{detail}</div>
      {connected && device && <div className="statusbar-cell optional">{device.serial}</div>}
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
        <span className="titlebar-brand">Android Backup Manager</span>
        <span className="titlebar-sep" />
        <DeviceChip />
        <nav className="titlebar-nav" aria-label="Secondary">
          <NavLink to="/history" className={({ isActive }) => (isActive ? "active" : "")}>
            History
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => (isActive ? "active" : "")}>
            Options
          </NavLink>
        </nav>
      </header>

      <UpdateBanner />
      <WorkflowRail />

      <div className="app-body">
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
      <UpdateProvider>
        <Shell />
      </UpdateProvider>
    </DeviceProvider>
  );
}
