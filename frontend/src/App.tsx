import { NavLink, Route, Routes } from "react-router-dom";
import Backup from "./pages/Backup";
import Cleanup from "./pages/Cleanup";
import Dashboard from "./pages/Dashboard";
import Discover from "./pages/Discover";
import History from "./pages/History";
import Settings from "./pages/Settings";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/discover", label: "Discover" },
  { to: "/backup", label: "Backup" },
  { to: "/cleanup", label: "Cleanup" },
  { to: "/history", label: "History" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Android Backup Manager</h1>
        <nav>
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main">
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
  );
}
