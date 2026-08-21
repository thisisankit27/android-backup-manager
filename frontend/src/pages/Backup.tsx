import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, Category, DiscoveredFile, DiscoveryResult, watchJob } from "../api/client";

type FileStateMap = Record<string, string>;

function fmtSize(n: number): string {
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${n} B`;
}

function categoryStats(cat: Category, states: FileStateMap) {
  let includedCount = 0, includedSize = 0;
  for (const f of cat.files) {
    if (states[f.path] === "INCLUDE") { includedCount++; includedSize += f.size; }
  }
  return { includedCount, includedSize, total: cat.files.length, totalSize: cat.files.reduce((s, f) => s + f.size, 0) };
}

export default function Backup() {
  const [params] = useSearchParams();
  const discoveryId = params.get("discovery");

  const [discovery, setDiscovery] = useState<DiscoveryResult | null>(null);
  const [states, setStates] = useState<FileStateMap>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [filterText, setFilterText] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const [step, setStep] = useState<"select" | "review" | "running" | "done">("select");
  const [selectionSummary, setSelectionSummary] = useState<any>(null);
  const [destParent, setDestParent] = useState("");
  const [progress, setProgress] = useState<{ done: number; total: number; phase: string }>({ done: 0, total: 0, phase: "" });
  const [backupResult, setBackupResult] = useState<any>(null);
  const [backupDir, setBackupDir] = useState<string>("");

  useEffect(() => {
    if (!discoveryId) return;
    api.getDiscovery(discoveryId).then((d) => {
      setDiscovery(d);
      const initial: FileStateMap = {};
      for (const cat of d.categories) for (const f of cat.files) initial[f.path] = f.default_state;
      setStates(initial);
    }).catch((e) => setError(e.message));
  }, [discoveryId]);

  const totals = useMemo(() => {
    let includedCount = 0, includedSize = 0, excludedCount = 0, excludedSize = 0;
    if (discovery) {
      for (const cat of discovery.categories) for (const f of cat.files) {
        if (states[f.path] === "INCLUDE") { includedCount++; includedSize += f.size; }
        else { excludedCount++; excludedSize += f.size; }
      }
    }
    return { includedCount, includedSize, excludedCount, excludedSize };
  }, [discovery, states]);

  if (!discoveryId) return <p>No discovery selected. Go to <b>Discover</b> first.</p>;
  if (error) return <div className="error-box">{error}</div>;
  if (!discovery) return <p>Loading discovery...</p>;

  const setCategoryState = (cat: Category, value: string) => {
    setStates((prev) => {
      const next = { ...prev };
      for (const f of cat.files) if (f.default_state !== "INACCESSIBLE") next[f.path] = value;
      return next;
    });
  };

  const setFileState = (f: DiscoveredFile, value: string) => {
    setStates((prev) => ({ ...prev, [f.path]: value }));
  };

  const doReview = async () => {
    const summary = await api.freezeSelection(discoveryId, states);
    setSelectionSummary(summary);
    setStep("review");
  };

  const doStartBackup = async () => {
    setStep("running");
    const { job_id, backup_dir } = await api.startBackup(selectionSummary.selection_id, destParent || undefined);
    setBackupDir(backup_dir);
    watchJob(
      job_id,
      (event) => {
        if (event.phase === "copied" || event.phase === "error") {
          setProgress({ done: event.done, total: event.total, phase: event.status || event.phase });
        } else {
          setProgress((p) => ({ ...p, phase: event.phase }));
        }
      },
      async (finalStatus, result, err) => {
        if (finalStatus === "done") {
          const manifest = await api.getManifest(backup_dir);
          setBackupResult({ ...result, manifest });
          setStep("done");
        } else {
          setError(err);
        }
      }
    );
  };

  if (step === "running") {
    const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : 0;
    return (
      <>
        <h2>Backing up...</h2>
        <div className="card">
          <div>{progress.phase} — {progress.done}/{progress.total} files</div>
          <div className="progress-bar"><div className="progress-bar-fill" style={{ width: `${pct}%` }} /></div>
        </div>
      </>
    );
  }

  if (step === "done" && backupResult) {
    const entries = backupResult.manifest.entries as any[];
    const verified = entries.filter((e) => e.verification_status === "verified").length;
    const failed = entries.length - verified;
    return (
      <>
        <h2>Backup complete</h2>
        <div className="summary-bar">
          <div className="stat"><strong>{entries.length}</strong>considered</div>
          <div className="stat"><strong className="badge verified" style={{ fontSize: 18 }}>{verified}</strong>verified</div>
          <div className="stat"><strong className={failed ? "badge failed" : ""} style={{ fontSize: 18 }}>{failed}</strong>failed</div>
          <div className="stat"><strong>{backupResult.manifest.duplicate_groups.length}</strong>duplicate groups</div>
        </div>
        <div className="card">
          <div className="dim">Backup directory</div>
          <div className="mono">{backupDir}</div>
        </div>
        {failed > 0 && (
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Failed files</h3>
            <table><tbody>
              {entries.filter((e) => e.verification_status !== "verified").map((e) => (
                <tr key={e.source_path}><td className="mono">{e.source_path}</td><td className="dim">{e.error}</td></tr>
              ))}
            </tbody></table>
          </div>
        )}
        <pre className="report">{backupResult.manifest.report_txt}</pre>
        <p className="dim">Deletion is a separate step. Go to the <b>Cleanup</b> page when you're ready to review what can safely be removed from the device.</p>
      </>
    );
  }

  if (step === "review") {
    const included = totals.includedCount;
    return (
      <>
        <h2>Review Backup</h2>
        <div className="warning-banner" style={{ borderColor: "var(--accent)", background: "rgba(79,140,255,0.08)", color: "var(--text)" }}>
          Nothing will be copied until you click <b>Start Backup</b> below.
        </div>
        <div className="card">
          <div className="summary-bar">
            <div className="stat"><strong>{included}</strong>files selected</div>
            <div className="stat"><strong>{fmtSize(totals.includedSize)}</strong>total size</div>
            <div className="stat"><strong>{totals.excludedCount}</strong>excluded</div>
          </div>
          <label className="dim">Backup destination parent directory (default: your Desktop)</label>
          <input type="text" placeholder="~/Desktop" value={destParent} onChange={(e) => setDestParent(e.target.value)} />
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Included categories</h3>
          <table><thead><tr><th>Category</th><th className="right">Files</th><th className="right">Size</th></tr></thead>
            <tbody>
              {discovery.categories.map((cat) => {
                const s = categoryStats(cat, states);
                if (s.includedCount === 0) return null;
                return <tr key={cat.id}><td>{cat.label}</td><td className="right">{s.includedCount}</td><td className="right">{fmtSize(s.includedSize)}</td></tr>;
              })}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Excluded categories / items</h3>
          <table><thead><tr><th>Category</th><th className="right">Excluded files</th></tr></thead>
            <tbody>
              {discovery.categories.map((cat) => {
                const s = categoryStats(cat, states);
                const excluded = s.total - s.includedCount;
                if (excluded === 0) return null;
                return <tr key={cat.id}><td>{cat.label}</td><td className="right">{excluded}</td></tr>;
              })}
            </tbody>
          </table>
        </div>
        {discovery.inaccessible.length > 0 && (
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Inaccessible locations</h3>
            {discovery.inaccessible.map((i) => <div key={i.path} className="dim">{i.path}: {i.reason}</div>)}
          </div>
        )}
        <div style={{ display: "flex", gap: 12 }}>
          <button onClick={() => setStep("select")}>Back to selection</button>
          <button className="primary" onClick={doStartBackup}>Start Backup</button>
        </div>
      </>
    );
  }

  return (
    <>
      <h2>Select files to back up</h2>
      <p className="subtitle">Device {discovery.device_serial} — discovered {discovery.categories.reduce((n, c) => n + c.files.length, 0)} files.</p>

      <div className="summary-bar">
        <div className="stat"><strong>{totals.includedCount}</strong>selected</div>
        <div className="stat"><strong>{fmtSize(totals.includedSize)}</strong>selected size</div>
        <div className="stat"><strong>{totals.excludedCount}</strong>excluded</div>
        <div className="stat"><strong>{fmtSize(totals.excludedSize)}</strong>excluded size</div>
      </div>

      {discovery.categories.map((cat) => {
        const s = categoryStats(cat, states);
        const isExpanded = !!expanded[cat.id];
        const filter = (filterText[cat.id] || "").toLowerCase();
        const visibleFiles = isExpanded ? cat.files.filter((f) => f.filename.toLowerCase().includes(filter)) : [];
        return (
          <div className="card" key={cat.id}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <input
                  type="checkbox"
                  checked={s.includedCount === s.total && s.total > 0}
                  ref={(el) => { if (el) el.indeterminate = s.includedCount > 0 && s.includedCount < s.total; }}
                  onChange={(e) => setCategoryState(cat, e.target.checked ? "INCLUDE" : "EXCLUDE")}
                />{" "}
                <b>{cat.label}</b>{" "}
                <span className="dim">({cat.report_group})</span>
                {!cat.default_include && <span className="badge skipped" style={{ marginLeft: 8 }}>excluded by default</span>}
              </div>
              <div>
                <span className="dim">{s.includedCount}/{s.total} files, {fmtSize(s.includedSize)}</span>{" "}
                <button onClick={() => setExpanded((p) => ({ ...p, [cat.id]: !p[cat.id] }))}>
                  {isExpanded ? "Collapse" : "Expand"}
                </button>
              </div>
            </div>
            {isExpanded && (
              <>
                <input
                  type="text"
                  placeholder="Filter by filename..."
                  style={{ margin: "10px 0" }}
                  value={filterText[cat.id] || ""}
                  onChange={(e) => setFilterText((p) => ({ ...p, [cat.id]: e.target.value }))}
                />
                <table>
                  <thead><tr><th></th><th>Filename</th><th className="right">Size</th><th>Flags</th></tr></thead>
                  <tbody>
                    {visibleFiles.slice(0, 500).map((f) => (
                      <tr key={f.path}>
                        <td>
                          <input
                            type="checkbox"
                            checked={states[f.path] === "INCLUDE"}
                            disabled={f.default_state === "INACCESSIBLE"}
                            onChange={(e) => setFileState(f, e.target.checked ? "INCLUDE" : "EXCLUDE")}
                          />
                        </td>
                        <td className="mono">{f.filename}</td>
                        <td className="right">{fmtSize(f.size)}</td>
                        <td>
                          {f.is_trashed && <span className="badge skipped">trashed</span>}{" "}
                          {f.crypt14_kind === "current" && <span className="badge protected">current DB</span>}{" "}
                          {f.crypt14_kind === "historical" && <span className="badge eligible">historical DB</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {visibleFiles.length > 500 && <p className="dim">Showing first 500 of {visibleFiles.length} matching files.</p>}
              </>
            )}
          </div>
        );
      })}

      <button className="primary" onClick={doReview} disabled={totals.includedCount === 0}>
        Review Backup ({totals.includedCount} files)
      </button>
    </>
  );
}
