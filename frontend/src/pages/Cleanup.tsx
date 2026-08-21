import { useEffect, useState } from "react";
import { api, watchJob } from "../api/client";

function fmtSize(n: number): string {
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${n} B`;
}

const REQUIRED_PHRASE = "DELETE VERIFIED BACKUPS";

export default function Cleanup() {
  const [backupDir, setBackupDir] = useState("");
  const [knownBackups, setKnownBackups] = useState<any[]>([]);
  const [step, setStep] = useState<"pick" | "previewing" | "preview" | "confirm" | "deleting" | "done">("pick");
  const [preview, setPreview] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [phraseInput, setPhraseInput] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [deletionResult, setDeletionResult] = useState<any>(null);

  useEffect(() => {
    api.history().then((h) => setKnownBackups(h.filter((e) => e.type === "backup")));
  }, []);

  const runPreview = async () => {
    setError(null);
    setStep("previewing");
    try {
      const { job_id } = await api.startDeletionPreview(backupDir);
      watchJob(job_id, () => {}, async (finalStatus, result, err) => {
        if (finalStatus === "done") {
          const full = await api.getPreview(backupDir, result.preview_id);
          setPreview(full);
          setStep("preview");
        } else {
          setError(err);
          setStep("pick");
        }
      });
    } catch (e: any) {
      setError(e.message);
      setStep("pick");
    }
  };

  const runDeletion = async () => {
    setStep("deleting");
    const { job_id } = await api.executeDeletion({
      backup_dir: backupDir,
      preview_id: preview.id,
      confirmation_phrase: phraseInput,
      preview_acknowledged: acknowledged,
      dry_run: dryRun,
    });
    watchJob(
      job_id,
      (event) => { if (event.phase === "progress") setProgress({ done: event.done, total: event.total }); },
      (finalStatus, result, err) => {
        if (finalStatus === "done") { setDeletionResult(result); setStep("done"); }
        else { setError(err); setStep("preview"); }
      }
    );
  };

  if (step === "pick") {
    return (
      <>
        <h2>Cleanup</h2>
        <p className="subtitle">
          Deletion is a completely separate workflow from backup. Nothing here runs
          automatically after a backup finishes.
        </p>
        {error && <div className="error-box">{error}</div>}
        <div className="card">
          <label className="dim">Backup directory to verify against</label>
          <input type="text" placeholder="/home/you/Desktop/Android_Backup_..." value={backupDir}
                 onChange={(e) => setBackupDir(e.target.value)} />
          {knownBackups.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="dim" style={{ marginBottom: 6 }}>Or pick a known backup:</div>
              {knownBackups.map((b) => (
                <button key={b.id} style={{ marginRight: 8, marginBottom: 8 }} onClick={() => setBackupDir(b.backup_dir)}>
                  {b.timestamp} ({b.verified}/{b.files} verified)
                </button>
              ))}
            </div>
          )}
          <div style={{ marginTop: 16 }}>
            <button className="primary" onClick={runPreview} disabled={!backupDir}>
              Run Fresh Verification
            </button>
          </div>
        </div>
      </>
    );
  }

  if (step === "previewing") {
    return <><h2>Cleanup</h2><p>Re-verifying every file against the device and the backup...</p></>;
  }

  if (step === "preview" && preview) {
    return (
      <>
        <h2>Deletion Preview</h2>
        <div className="warning-banner">
          <strong>Read only.</strong> No files have been deleted. Review carefully before authorizing deletion.
        </div>
        <div className="summary-bar">
          <div className="stat"><strong>{preview.eligible.length}</strong>eligible</div>
          <div className="stat"><strong>{fmtSize(preview.eligible.reduce((s: number, c: any) => s + c.size, 0))}</strong>eligible size</div>
          <div className="stat"><strong>{preview.skipped.length}</strong>skipped</div>
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>WhatsApp .crypt14 databases</h3>
          <table><thead><tr><th>File</th><th>Kind</th><th>Status</th></tr></thead>
            <tbody>
              {preview.crypt14_inventory.map((c: any) => (
                <tr key={c.source_path}>
                  <td className="mono">{c.filename}</td>
                  <td>{c.kind}</td>
                  <td>{c.eligible ? <span className="badge eligible">eligible</span> : <span className="badge protected">protected</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>Skipped ({preview.skipped.length})</h3>
          {preview.skipped.length === 0 ? <p className="dim">None.</p> : (
            <table><thead><tr><th>Path</th><th>Reason</th></tr></thead>
              <tbody>
                {preview.skipped.slice(0, 200).map((s: any) => (
                  <tr key={s.source_path}><td className="mono">{s.source_path}</td><td><span className="badge skipped">{s.reason}</span></td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <pre className="report">{preview.report_txt}</pre>

        <button className="danger" onClick={() => setStep("confirm")} disabled={preview.eligible.length === 0}>
          Proceed to Deletion Authorization
        </button>
      </>
    );
  }

  if (step === "confirm") {
    return (
      <>
        <h2>Explicit Deletion Authorization</h2>
        <div className="warning-banner">
          <strong>This will permanently delete {preview.eligible.length} verified files
          ({fmtSize(preview.eligible.reduce((s: number, c: any) => s + c.size, 0))}) from the Android device.</strong>
          <br />Backup copies of every file are already safely stored and will not be affected.
        </div>
        <div className="card">
          <p>Type <code>{REQUIRED_PHRASE}</code> to confirm:</p>
          <input type="text" value={phraseInput} onChange={(e) => setPhraseInput(e.target.value)} />
          <label style={{ display: "block", marginTop: 16 }}>
            <input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} />{" "}
            I have reviewed the deletion preview above and understand this action is permanent.
          </label>
          <label style={{ display: "block", marginTop: 8 }}>
            <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />{" "}
            Dry run only (verify everything, delete nothing)
          </label>
          <div style={{ display: "flex", gap: 12, marginTop: 20 }}>
            <button onClick={() => setStep("preview")}>Back</button>
            <button className="danger" onClick={runDeletion}
                    disabled={phraseInput !== REQUIRED_PHRASE || !acknowledged}>
              {dryRun ? "Run Dry Run" : "Delete Verified Files"}
            </button>
          </div>
        </div>
      </>
    );
  }

  if (step === "deleting") {
    const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : 0;
    return (
      <>
        <h2>{dryRun ? "Dry run in progress..." : "Deleting..."}</h2>
        <div className="card">
          <div>{progress.done}/{progress.total} files</div>
          <div className="progress-bar"><div className="progress-bar-fill" style={{ width: `${pct}%` }} /></div>
        </div>
      </>
    );
  }

  if (step === "done" && deletionResult) {
    return (
      <>
        <h2>{dryRun ? "Dry run complete" : "Deletion complete"}</h2>
        {deletionResult.aborted_reason && (
          <div className="warning-banner">
            <strong>Stopped early:</strong> {deletionResult.aborted_reason}
          </div>
        )}
        <div className="summary-bar">
          <div className="stat"><strong>{deletionResult.deleted_count}</strong>{dryRun ? "would delete" : "deleted"}</div>
          <div className="stat"><strong>{fmtSize(deletionResult.deleted_size)}</strong>size</div>
          <div className="stat"><strong>{deletionResult.skipped_count}</strong>skipped</div>
        </div>
        <pre className="report">{deletionResult.report_txt}</pre>
      </>
    );
  }

  return null;
}
