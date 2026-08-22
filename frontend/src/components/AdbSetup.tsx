import { useState } from "react";
import { AdbStatus, api, watchJob } from "../api/client";

/** Shown when adb is missing. A blocked prerequisite is the whole screen's
 * business, not a truncated line in the status bar — so it gets a panel with
 * the one action that fixes it. */
export function AdbSetup({ status, onInstalled }: { status: AdbStatus; onInstalled: () => void }) {
  const [phase, setPhase] = useState<"idle" | "running" | "error">("idle");
  const [detail, setDetail] = useState("");
  const [error, setError] = useState<string | null>(null);

  const install = async () => {
    setPhase("running");
    setError(null);
    setDetail("starting...");
    try {
      const { job_id } = await api.installAdb();
      watchJob(
        job_id,
        (e) => {
          if (e.phase === "downloading") setDetail("Downloading from dl.google.com...");
          else if (e.phase === "extracting") setDetail("Extracting...");
          else if (e.phase === "done") setDetail("Installed.");
        },
        (finalStatus, _result, err) => {
          if (finalStatus === "done") onInstalled();
          else { setPhase("error"); setError(err); }
        }
      );
    } catch (e: any) {
      setPhase("error");
      setError(e.message);
    }
  };

  return (
    <>
      <div className="notice warn">
        <span>
          <strong>Android Platform Tools are required.</strong> This app talks to your phone
          through <span className="mono">adb</span>, which isn't installed yet. Your device
          can't be detected until it is.
        </span>
      </div>

      <div className="panel">
        <div className="panel-head">Set Up adb</div>
        <div className="panel-body">
          <p style={{ margin: "0 0 12px" }}>
            Download the official Android Platform Tools from Google. They're saved inside
            this app's own folder — nothing else on your system is changed, and no
            administrator rights are needed.
          </p>

          {status.download_url && (
            <table className="propgrid" style={{ marginBottom: 14 }}>
              <tbody>
                <tr><th>Source</th><td className="mono">{status.download_url}</td></tr>
                <tr><th>Size</th><td>about 10 MB</td></tr>
              </tbody>
            </table>
          )}

          {phase === "running" ? (
            <>
              <div className="progress">
                <div className="progress-fill" style={{ width: "100%", opacity: 0.35 }} />
              </div>
              <div className="dim" style={{ marginTop: 8 }}>{detail}</div>
            </>
          ) : (
            <button className="primary" onClick={install}>Download and Install</button>
          )}

          {error && (
            <div className="notice error" style={{ marginTop: 14, marginBottom: 0 }}>
              <span><strong>Install failed.</strong> {error}</span>
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">Or Install It Yourself</div>
        <div className="panel-body">
          <pre className="report" style={{ maxHeight: 200, whiteSpace: "pre-wrap" }}>
            {status.hint}
          </pre>
          <div className="hint" style={{ marginTop: 8 }}>
            Already have it somewhere unusual? Set{" "}
            <span className="mono">{status.env_override}</span> to the full path of the
            executable and restart the app.
          </div>
        </div>
      </div>
    </>
  );
}
