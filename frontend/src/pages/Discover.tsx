import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, watchJob } from "../api/client";
import { useDevice } from "../state/device";
import { setLastDiscoveryId } from "../state/discovery";

const SCANNED = [
  "DCIM / Camera and other camera folders",
  "Pictures / Screenshots",
  "Movies",
  "Downloads and Documents",
  "WhatsApp media, databases and backups",
  "Any other user-created top-level folder",
];

export default function Discover() {
  const [status, setStatus] = useState<"idle" | "running" | "error">("idle");
  const [phase, setPhase] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { status: device } = useDevice();
  const navigate = useNavigate();

  const start = async () => {
    setStatus("running");
    setError(null);
    try {
      const { job_id } = await api.startDiscovery();
      watchJob(
        job_id,
        (event) => setPhase(event.phase),
        (finalStatus, result, err) => {
          if (finalStatus === "done") {
            setLastDiscoveryId(result.discovery_id);
            navigate(`/backup?discovery=${result.discovery_id}`);
          } else {
            setStatus("error");
            setError(err);
          }
        }
      );
    } catch (e: any) {
      setStatus("error");
      setError(e.message);
    }
  };

  const running = status === "running";

  return (
    <>
      <div className="page-head">
        <h1>Discover</h1>
        <p className="page-sub">Read-only scan of accessible device storage.</p>
      </div>

      {error && <div className="notice error"><span><strong>Scan failed.</strong> {error}</span></div>}

      <div className="notice info">
        <span>
          Discovery is <strong>read-only</strong>. Nothing on the device is modified, copied
          or deleted during this step.
        </span>
      </div>

      <div className="panel">
        <div className="panel-head">Locations Scanned</div>
        <div className="panel-body">
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {SCANNED.map((s) => <li key={s}>{s}</li>)}
          </ul>
          <div className="hint" style={{ marginTop: 8 }}>
            App-private locations (<span className="mono">Android/data/…</span>) are reported by
            name only — Android does not permit reading their contents.
          </div>
        </div>
      </div>

      {running && (
        <div className="panel">
          <div className="panel-head">Scanning</div>
          <div className="panel-body">
            <div className="progress">
              <div className="progress-fill" style={{ width: "100%", opacity: 0.35 }} />
            </div>
            <table className="propgrid" style={{ marginTop: 12 }}>
              <tbody>
                <tr><th>Phase</th><td>{phase || "starting..."}</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="wizard-footer">
        <span className="dim">
          {device?.connected
            ? `Target: ${device.device?.manufacturer} ${device.device?.model}`
            : "No device connected."}
        </span>
        <span className="spacer" />
        <button className="primary" onClick={start} disabled={running || !device?.connected}>
          {running ? "Scanning..." : "Start Scan"}
        </button>
      </div>
    </>
  );
}
