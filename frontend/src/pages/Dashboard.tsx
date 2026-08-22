import { Link } from "react-router-dom";
import { fmtSize } from "../lib/format";
import { useDevice } from "../state/device";

export default function Dashboard() {
  const { status, loading, error, refresh } = useDevice();
  const dev = status?.device;

  return (
    <>
      <div className="page-head">
        <h1>Device</h1>
        <p className="page-sub">Connection state and recent activity.</p>
        <span className="spacer" />
        <button onClick={refresh} disabled={loading}>{loading ? "Checking..." : "Refresh"}</button>
      </div>

      {error && <div className="notice error"><span><strong>Error.</strong> {error}</span></div>}

      <div className="panel">
        <div className="panel-head">
          Connection
          <span className="spacer" />
          {status?.connected
            ? <span className="badge connected">CONNECTED</span>
            : <span className="badge disconnected">NOT CONNECTED</span>}
        </div>
        <div className="panel-body">
          {status?.connected && dev ? (
            <table className="propgrid">
              <tbody>
                <tr><th>Model</th><td>{dev.manufacturer} {dev.model}</td></tr>
                <tr><th>Android version</th><td>{dev.android_version} (SDK {dev.sdk})</td></tr>
                <tr><th>Serial</th><td className="mono">{dev.serial}</td></tr>
                <tr>
                  <th>Storage</th>
                  <td>
                    {fmtSize(dev.storage_used_bytes)} used of {fmtSize(dev.storage_total_bytes)}
                    <span className="dim"> ({fmtSize(dev.storage_free_bytes)} free)</span>
                  </td>
                </tr>
              </tbody>
            </table>
          ) : (
            <div className="dim">
              {status?.reason || "Checking..."}
              <ol style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                <li>Connect the phone over USB.</li>
                <li>Enable USB debugging in Developer Options.</li>
                <li>Accept the "Allow USB debugging?" prompt on the device.</li>
              </ol>
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">Recent Activity</div>
        <div className="panel-body">
          <table className="propgrid">
            <tbody>
              <tr>
                <th>Last backup</th>
                <td>
                  {status?.last_backup
                    ? `${status.last_backup.timestamp} — ${status.last_backup.verified}/${status.last_backup.files} verified`
                    : <span className="dim">none yet</span>}
                </td>
              </tr>
              <tr>
                <th>Last deletion preview</th>
                <td>
                  {status?.last_deletion_preview
                    ? `${status.last_deletion_preview.timestamp} — ${status.last_deletion_preview.eligible} eligible`
                    : <span className="dim">none yet</span>}
                </td>
              </tr>
              <tr>
                <th>Last deletion</th>
                <td>
                  {status?.last_deletion
                    ? `${status.last_deletion.timestamp} — ${status.last_deletion.deleted} deleted`
                    : <span className="dim">none yet</span>}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="wizard-footer">
        <span className="spacer" />
        <Link to="/history"><button>View History</button></Link>
        <Link to="/discover">
          <button className="primary" disabled={!status?.connected}>Discover Device...</button>
        </Link>
      </div>
    </>
  );
}
