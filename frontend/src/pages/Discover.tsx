import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, watchJob } from "../api/client";
import { setLastDiscoveryId } from "../state/discovery";

export default function Discover() {
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [phase, setPhase] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
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
            setStatus("done");
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

  return (
    <>
      <h2>Discover</h2>
      <p className="subtitle">
        Read-only scan of accessible storage. Nothing on the device is modified, copied, or
        deleted during discovery.
      </p>

      {error && <div className="error-box">{error}</div>}

      <div className="card">
        <p>
          This inspects Camera, Screenshots, Downloads, Documents, WhatsApp media, and any
          other user-created folders on the connected device, and reports (but does not read
          into) app-private locations it cannot access.
        </p>
        <button className="primary" onClick={start} disabled={status === "running"}>
          {status === "running" ? `Discovering... (${phase})` : "Discover"}
        </button>
      </div>
    </>
  );
}
