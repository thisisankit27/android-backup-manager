import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, DeviceStatus } from "../api/client";

function fmtBytes(n: number | null | undefined): string {
  if (n == null) return "unknown";
  const gb = n / 1024 ** 3;
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(n / 1024 ** 2).toFixed(0)} MB`;
}

export default function Dashboard() {
  const [status, setStatus] = useState<DeviceStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    setLoading(true);
    setError(null);
    api
      .deviceStatus()
      .then(setStatus)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(refresh, []);

  return (
    <>
      <h2>Dashboard</h2>
      <p className="subtitle">Device connection state and recent activity.</p>

      {error && <div className="error-box">{error}</div>}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            {status?.connected ? (
              <>
                <span className="badge connected">CONNECTED</span>
                <div style={{ marginTop: 12 }}>
                  <strong>{status.device?.manufacturer} {status.device?.model}</strong>
                  <div className="dim">Android {status.device?.android_version} (SDK {status.device?.sdk})</div>
                  <div className="dim mono">{status.device?.serial}</div>
                  {status.device?.storage_total_bytes != null && (
                    <div className="dim" style={{ marginTop: 6 }}>
                      Storage: {fmtBytes(status.device.storage_used_bytes)} used /{" "}
                      {fmtBytes(status.device.storage_total_bytes)} total (
                      {fmtBytes(status.device.storage_free_bytes)} free)
                    </div>
                  )}
                </div>
              </>
            ) : (
              <>
                <span className="badge disconnected">NOT CONNECTED</span>
                <div className="dim" style={{ marginTop: 12 }}>
                  {status?.reason || "Checking..."}
                  <br />
                  Connect your Android phone via USB, enable USB debugging in Developer
                  Options, and accept the "Allow USB debugging?" prompt on the device.
                </div>
              </>
            )}
          </div>
          <button onClick={refresh} disabled={loading}>
            {loading ? "Checking..." : "Refresh"}
          </button>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Recent activity</h3>
        <table>
          <tbody>
            <tr>
              <td>Last backup</td>
              <td>
                {status?.last_backup
                  ? `${status.last_backup.timestamp} — ${status.last_backup.verified}/${status.last_backup.files} verified`
                  : <span className="dim">none yet</span>}
              </td>
            </tr>
            <tr>
              <td>Last deletion preview</td>
              <td>
                {status?.last_deletion_preview
                  ? `${status.last_deletion_preview.timestamp} — ${status.last_deletion_preview.eligible} eligible`
                  : <span className="dim">none yet</span>}
              </td>
            </tr>
            <tr>
              <td>Last deletion</td>
              <td>
                {status?.last_deletion
                  ? `${status.last_deletion.timestamp} — ${status.last_deletion.deleted} deleted`
                  : <span className="dim">none yet</span>}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <Link to="/discover"><button className="primary" disabled={!status?.connected}>Discover Device</button></Link>
        <Link to="/history"><button>View History</button></Link>
      </div>
    </>
  );
}
