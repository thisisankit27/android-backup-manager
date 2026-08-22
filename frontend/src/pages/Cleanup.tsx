import { useEffect, useState } from "react";
import { api, watchJob } from "../api/client";
import { Link } from "react-router-dom";
import { EmptyState, IconArchive } from "../components/EmptyState";
import { fmtCount, fmtSize } from "../lib/format";

const REQUIRED_PHRASE = "DELETE VERIFIED BACKUPS";

type Step = "pick" | "previewing" | "preview" | "confirm" | "deleting" | "done";

export default function Cleanup() {
  const [backupDir, setBackupDir] = useState("");
  const [knownBackups, setKnownBackups] = useState<any[]>([]);
  const [step, setStep] = useState<Step>("pick");
  const [preview, setPreview] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [phraseInput, setPhraseInput] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [deletionResult, setDeletionResult] = useState<any>(null);

  useEffect(() => {
    api.history()
      .then((h) => {
        const backups = h.filter((e) => e.type === "backup");
        setKnownBackups(backups);
        // History arrives newest-first. Preselecting the most recent backup
        // is what people almost always mean, and it means this page never
        // opens on an empty path box with no way to guess what goes in it.
        if (backups.length > 0) setBackupDir((current) => current || backups[0].backup_dir);
      })
      .catch(() => {});
  }, []);

  const eligibleSize = preview
    ? preview.eligible.reduce((s: number, c: any) => s + c.size, 0)
    : 0;

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

  const head = (sub: string) => (
    <div className="page-head">
      <h1>Cleanup</h1>
      <p className="page-sub">{sub}</p>
    </div>
  );

  /* ---------------------------------------------------------------- pick */

  if (step === "pick") {
    return (
      <>
        {head("Choose a verified backup to check the device against.")}

        {error && <div className="notice error"><span><strong>Error.</strong> {error}</span></div>}

        <div className="notice warn">
          <span>
            Deletion is a completely separate workflow from backup. Nothing here runs
            automatically after a backup finishes.
          </span>
        </div>

        <div className="panel">
          <div className="panel-head">
            Your Backups
            <span className="spacer" />
            {knownBackups.length > 0 && (
              <span className="badge info">{fmtCount(knownBackups.length)}</span>
            )}
          </div>
          <div className="panel-body flush scroll-y">
            {knownBackups.length === 0 ? (
              <EmptyState
                icon={IconArchive}
                title="There is no verified backup to check against"
                actions={<Link to="/backup"><button className="primary">Back up first</button></Link>}
              >
                Nothing can be deleted from the phone until its files exist somewhere else
                and have been proven identical. Make a backup, and this page will be able
                to work out what is safe to remove.
              </EmptyState>
            ) : (
              <table className="grid">
                <thead>
                  <tr><th>When</th><th className="right">Verified</th><th>Folder</th><th /></tr>
                </thead>
                <tbody>
                  {knownBackups.map((b) => (
                    <tr key={b.id}>
                      <td className="mono">{b.timestamp}</td>
                      <td className="right">
                        {b.verified === b.files ? (
                          <span className="badge verified">{b.verified}/{b.files}</span>
                        ) : (
                          <span className="badge warn">{b.verified}/{b.files}</span>
                        )}
                      </td>
                      <td className="mono">{b.backup_dir}</td>
                      <td className="right">
                        {b.backup_dir === backupDir ? (
                          <span className="badge info">SELECTED</span>
                        ) : (
                          <button onClick={() => setBackupDir(b.backup_dir)}>Select</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">Or Point At A Folder</div>
          <div className="panel-body">
            <div className="field">
              <label htmlFor="bdir">Backup folder to verify the device against</label>
              <input
                id="bdir"
                type="text"
                placeholder="/home/you/Desktop/Android_Backup_..."
                value={backupDir}
                onChange={(e) => setBackupDir(e.target.value)}
              />
              <div className="hint">
                Only needed for a backup made on another machine, or one this app has no
                record of.
              </div>
            </div>
          </div>
        </div>

        <div className="wizard-footer">
          <span className="dim">
            {backupDir
              ? "Every file will be re-hashed on the device before anything is deleted."
              : "Choose a backup to continue."}
          </span>
          <span className="spacer" />
          <button className="primary" onClick={runPreview} disabled={!backupDir}>
            Verify against this backup
          </button>
        </div>
      </>
    );
  }

  /* ---------------------------------------------------------- previewing */

  if (step === "previewing") {
    return (
      <>
        {head("Re-verifying every file against the device and the backup.")}
        <div className="panel">
          <div className="panel-head">Verifying</div>
          <div className="panel-body">
            <div className="progress">
              <div className="progress-fill" style={{ width: "100%", opacity: 0.35 }} />
            </div>
            <div className="dim" style={{ marginTop: 8 }}>
              Re-hashing every backed-up file on the device. Nothing is deleted during this step.
            </div>
          </div>
        </div>
      </>
    );
  }

  /* ------------------------------------------------------------- preview */

  if (step === "preview" && preview) {
    return (
      <>
        {head("Review exactly what would be deleted.")}

        {error && <div className="notice error"><span><strong>Error.</strong> {error}</span></div>}

        <div className="notice info">
          <span><strong>Read only.</strong> No files have been deleted.</span>
        </div>

        <div className="statstrip">
          <div className="stat"><strong>{fmtCount(preview.eligible.length)}</strong>eligible</div>
          <div className="stat"><strong>{fmtSize(eligibleSize)}</strong>reclaimable</div>
          <div className="stat"><strong>{fmtCount(preview.skipped.length)}</strong>skipped</div>
        </div>

        <div className="panel">
          <div className="panel-head">WhatsApp .crypt14 Databases</div>
          <div className="panel-body flush scroll-y">
            <table className="grid">
              <thead><tr><th>File</th><th>Kind</th><th>Status</th></tr></thead>
              <tbody>
                {preview.crypt14_inventory.map((c: any) => (
                  <tr key={c.source_path}>
                    <td className="mono">{c.filename}</td>
                    <td>{c.kind}</td>
                    <td>
                      {c.eligible
                        ? <span className="badge eligible">eligible</span>
                        : <span className="badge protected">protected</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            Skipped
            <span className="spacer" />
            <span className="dim">{fmtCount(preview.skipped.length)}</span>
          </div>
          <div className="panel-body flush scroll-y">
            {preview.skipped.length === 0 ? (
              <div className="placeholder inline">Nothing skipped.</div>
            ) : (
              <table className="grid">
                <thead><tr><th>Path</th><th>Reason</th></tr></thead>
                <tbody>
                  {preview.skipped.slice(0, 200).map((s: any) => (
                    <tr key={s.source_path}>
                      <td className="mono">{s.source_path}</td>
                      <td><span className="badge skipped">{s.reason}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">Report</div>
          <div className="panel-body flush">
            <pre className="report" style={{ border: "none" }}>{preview.report_txt}</pre>
          </div>
        </div>

        <div className="wizard-footer">
          <span className="dim">{fmtCount(preview.eligible.length)} file(s) eligible, {fmtSize(eligibleSize)}</span>
          <span className="spacer" />
          <button onClick={() => { setPreview(null); setStep("pick"); }}>&lt; Back</button>
          <button
            className="danger"
            onClick={() => setStep("confirm")}
            disabled={preview.eligible.length === 0}
          >
            Continue to Authorization &gt;
          </button>
        </div>
      </>
    );
  }

  /* ------------------------------------------------------------- confirm */

  if (step === "confirm") {
    const phraseOk = phraseInput === REQUIRED_PHRASE;
    return (
      <>
        {head("Explicit authorization required.")}

        <div className="notice error">
          <span>
            <strong>
              This permanently deletes {fmtCount(preview.eligible.length)} verified file(s)
              ({fmtSize(eligibleSize)}) from the device.
            </strong>
            <br />
            Backup copies of every one of these files are already stored and hash-verified,
            and are not affected by this operation.
          </span>
        </div>

        <div className="panel">
          <div className="panel-head">Confirmation</div>
          <div className="panel-body">
            <div className="field">
              <label htmlFor="phrase">
                Type <span className="mono">{REQUIRED_PHRASE}</span> to confirm
              </label>
              <input
                id="phrase"
                type="text"
                value={phraseInput}
                onChange={(e) => setPhraseInput(e.target.value)}
                autoComplete="off"
              />
              {phraseInput && !phraseOk && (
                <div className="hint" style={{ color: "var(--red)" }}>Phrase does not match.</div>
              )}
            </div>

            <div className="check-row">
              <input
                id="ack"
                type="checkbox"
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
              />
              <label htmlFor="ack">
                I have reviewed the deletion preview and understand this action is permanent.
              </label>
            </div>

            <div className="check-row">
              <input
                id="dry"
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
              />
              <label htmlFor="dry">
                Dry run only — verify everything, delete nothing.
              </label>
            </div>
          </div>
        </div>

        <div className="wizard-footer">
          <span className="spacer" />
          <button onClick={() => setStep("preview")}>&lt; Back</button>
          <button className="danger" onClick={runDeletion} disabled={!phraseOk || !acknowledged}>
            {dryRun ? "Run Dry Run" : "Delete Files"}
          </button>
        </div>
      </>
    );
  }

  /* ------------------------------------------------------------ deleting */

  if (step === "deleting") {
    const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : 0;
    return (
      <>
        {head(dryRun ? "Dry run in progress — nothing is being deleted." : "Deleting — do not disconnect the device.")}
        <div className="panel">
          <div className="panel-head">
            {dryRun ? "Dry Run" : "Deleting"}
            <span className="spacer" />
            <span className="dim">{pct}%</span>
          </div>
          <div className="panel-body">
            <div className="progress"><div className="progress-fill" style={{ width: `${pct}%` }} /></div>
            <div className="dim" style={{ marginTop: 8 }}>
              {fmtCount(progress.done)} / {fmtCount(progress.total)} files
            </div>
          </div>
        </div>
      </>
    );
  }

  /* ---------------------------------------------------------------- done */

  if (step === "done" && deletionResult) {
    return (
      <>
        {head(dryRun ? "Dry run complete." : "Deletion complete.")}

        {deletionResult.aborted_reason && (
          <div className="notice warn">
            <span><strong>Stopped early:</strong> {deletionResult.aborted_reason}</span>
          </div>
        )}

        <div className="statstrip">
          <div className="stat">
            <strong>{fmtCount(deletionResult.deleted_count)}</strong>
            {dryRun ? "would delete" : "deleted"}
          </div>
          <div className="stat"><strong>{fmtSize(deletionResult.deleted_size)}</strong>reclaimed</div>
          <div className="stat"><strong>{fmtCount(deletionResult.skipped_count)}</strong>skipped</div>
        </div>

        <div className="panel">
          <div className="panel-head">Report</div>
          <div className="panel-body flush">
            <pre className="report" style={{ border: "none" }}>{deletionResult.report_txt}</pre>
          </div>
        </div>

        <div className="wizard-footer">
          <span className="spacer" />
          <button onClick={() => {
            setStep("pick");
            setPreview(null);
            setDeletionResult(null);
            setPhraseInput("");
            setAcknowledged(false);
          }}>Done</button>
        </div>
      </>
    );
  }

  return null;
}
