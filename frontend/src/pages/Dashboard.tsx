import { Link } from "react-router-dom";
import { AdbSetup } from "../components/AdbSetup";
import { EmptyState, IconPhone } from "../components/EmptyState";
import { fmtSize } from "../lib/format";
import { useDevice } from "../state/device";

export default function Dashboard() {
  const { status, adb, loading, error, refresh } = useDevice();
  const dev = status?.device;

  // A missing adb blocks everything downstream, so it replaces the page
  // rather than sitting alongside a "not connected" panel that can't be
  // acted on.
  if (adb && !adb.found) {
    return (
      <>
        <div className="page-head">
          <h1>Setup Required</h1>
          <p className="page-sub">One prerequisite is missing.</p>
          <span className="spacer" />
          <button onClick={refresh} disabled={loading}>Re-check</button>
        </div>
        <AdbSetup status={adb} onInstalled={refresh} />
      </>
    );
  }

  return (
    <>
      <div className="page-head">
        <h1>Connect</h1>
        <p className="page-sub">Everything else starts here.</p>
        <span className="spacer" />
        <button onClick={refresh} disabled={loading}>{loading ? "Checking..." : "Re-check"}</button>
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
            <EmptyState icon={IconPhone} title="No phone is connected">
              <ol className="steplist" style={{ marginTop: 4 }}>
                <li>Connect the phone to this computer with a USB cable.</li>
                <li>
                  On the phone, turn on <strong>USB debugging</strong> in Developer
                  Options.
                </li>
                <li>
                  Tap <strong>Allow</strong> on the "Allow USB debugging?" prompt that
                  appears on the phone.
                </li>
                <li>Press Re-check below.</li>
              </ol>
            </EmptyState>
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
        {!status?.connected && (
          <span className="dim">Connect a phone to continue.</span>
        )}
        <span className="spacer" />
        <Link to="/history"><button>View history</button></Link>
        {status?.connected ? (
          <Link to="/discover"><button className="primary">Scan this device</button></Link>
        ) : (
          <button className="primary" disabled>Scan this device</button>
        )}
      </div>
    </>
  );
}
