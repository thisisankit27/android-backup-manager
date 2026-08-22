import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, Category, DiscoveredFile, DiscoveryResult, watchJob } from "../api/client";
import {
  allFolderKeys,
  buildFolderTree,
  FileStateMap,
  FileTree,
  filterTree,
  FolderNode,
} from "../components/FileTree";
import { EmptyState, IconSearch } from "../components/EmptyState";
import { fmtCount, fmtSize } from "../lib/format";
import { getLastDiscoveryId, setLastDiscoveryId } from "../state/discovery";

function categoryStats(cat: Category, states: FileStateMap) {
  let includedCount = 0, includedSize = 0;
  for (const f of cat.files) {
    if (states[f.path] === "INCLUDE") { includedCount++; includedSize += f.size; }
  }
  return { includedCount, includedSize, total: cat.files.length };
}

export default function Backup() {
  const [params, setParams] = useSearchParams();
  const discoveryId = params.get("discovery") || getLastDiscoveryId();

  const [discovery, setDiscovery] = useState<DiscoveryResult | null>(null);
  const [states, setStates] = useState<FileStateMap>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [step, setStep] = useState<"select" | "review" | "running" | "done">("select");
  const [selectionSummary, setSelectionSummary] = useState<any>(null);
  const [destParent, setDestParent] = useState("");
  const [progress, setProgress] = useState({ done: 0, total: 0, phase: "" });
  const [backupResult, setBackupResult] = useState<any>(null);
  const [backupDir, setBackupDir] = useState("");

  useEffect(() => {
    if (!discoveryId) return;
    setLastDiscoveryId(discoveryId);
    if (!params.get("discovery")) setParams({ discovery: discoveryId }, { replace: true });
    api.getDiscovery(discoveryId).then((d) => {
      setDiscovery(d);
      const initial: FileStateMap = {};
      for (const cat of d.categories) for (const f of cat.files) initial[f.path] = f.default_state;
      setStates(initial);
    }).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  /** One root node per discovered category — the tree's top-level directories. */
  const roots = useMemo<FolderNode[]>(() => {
    if (!discovery) return [];
    return discovery.categories.map((cat) =>
      buildFolderTree(
        cat.id,
        cat.label,
        cat.remote_dir,
        cat.files,
        cat.default_include ? undefined : "excluded by default"
      )
    );
  }, [discovery]);

  const needle = filter.trim().toLowerCase();
  const displayRoots = useMemo(() => {
    if (!needle) return roots;
    return roots.map((r) => filterTree(r, needle)).filter((r): r is FolderNode => r !== null);
  }, [roots, needle]);

  // While filtering, show every surviving branch expanded so matches are visible.
  const effectiveExpanded = useMemo(() => {
    if (!needle) return expanded;
    return Object.fromEntries(allFolderKeys(displayRoots).map((k) => [k, true]));
  }, [needle, displayRoots, expanded]);

  const setFilesState = (files: DiscoveredFile[], value: string) => {
    setStates((prev) => {
      const next = { ...prev };
      for (const f of files) if (f.default_state !== "INACCESSIBLE") next[f.path] = value;
      return next;
    });
  };

  const setAll = (value: string) => {
    if (!discovery) return;
    setStates((prev) => {
      const next = { ...prev };
      for (const cat of discovery.categories)
        for (const f of cat.files) if (f.default_state !== "INACCESSIBLE") next[f.path] = value;
      return next;
    });
  };

  const expandAll = () =>
    setExpanded(Object.fromEntries(allFolderKeys(roots).map((k) => [k, true])));
  const collapseAll = () => setExpanded({});

  const doReview = async () => {
    if (!discoveryId) return;
    setError(null);
    try {
      const summary = await api.freezeSelection(discoveryId, states);
      setSelectionSummary(summary);
      setStep("review");
    } catch (e: any) {
      setError(e.message);
    }
  };

  const doStartBackup = async () => {
    setError(null);
    setStep("running");
    const { job_id, backup_dir } = await api.startBackup(
      selectionSummary.selection_id,
      destParent || undefined
    );
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
          setStep("review");
        }
      }
    );
  };

  /* ---------------------------------------------------------------- gates */

  if (!discoveryId) {
    return (
      <>
        <div className="page-head">
          <h1>Back Up</h1>
          <p className="page-sub">Choose what to copy across, then verify every file.</p>
        </div>
        <div className="panel">
          <EmptyState
            icon={IconSearch}
            title="Nothing has been discovered yet"
            actions={<Link to="/discover"><button className="primary">Scan the device</button></Link>}
          >
            There is nothing to choose from until the device has been scanned. The scan is
            read-only — it reads names, sizes and hashes, and changes nothing on the phone.
          </EmptyState>
        </div>
      </>
    );
  }

  if (error && !discovery) {
    return (
      <>
        <div className="page-head"><h1>Back Up</h1></div>
        <div className="notice error"><span><strong>Error.</strong> {error}</span></div>
      </>
    );
  }

  if (!discovery) {
    return (
      <>
        <div className="page-head"><h1>Back Up</h1></div>
        <div className="panel"><div className="placeholder">Loading discovery...</div></div>
      </>
    );
  }

  const totalFiles = discovery.categories.reduce((n, c) => n + c.files.length, 0);

  /* ------------------------------------------------------------- running */

  if (step === "running") {
    const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : 0;
    return (
      <>
        <div className="page-head">
          <h1>Backing Up</h1>
          <p className="page-sub">Copying and verifying — do not disconnect the device.</p>
        </div>
        <div className="panel">
          <div className="panel-head">Progress<span className="spacer" /><span className="dim">{pct}%</span></div>
          <div className="panel-body">
            <div className="progress"><div className="progress-fill" style={{ width: `${pct}%` }} /></div>
            <table className="propgrid" style={{ marginTop: 12 }}>
              <tbody>
                <tr><th>Phase</th><td>{progress.phase || "starting..."}</td></tr>
                <tr><th>Files</th><td>{fmtCount(progress.done)} / {fmtCount(progress.total)}</td></tr>
                <tr><th>Destination</th><td className="mono">{backupDir}</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </>
    );
  }

  /* ---------------------------------------------------------------- done */

  if (step === "done" && backupResult) {
    const entries = backupResult.manifest.entries as any[];
    const verified = entries.filter((e) => e.verification_status === "verified").length;
    const failed = entries.length - verified;
    return (
      <>
        <div className="page-head">
          <h1>Backup Complete</h1>
          <p className="page-sub">Every copy was hash-verified against the source.</p>
        </div>

        <div className="statstrip">
          <div className="stat"><strong>{fmtCount(entries.length)}</strong>considered</div>
          <div className="stat"><strong>{fmtCount(verified)}</strong>verified</div>
          <div className="stat"><strong>{fmtCount(failed)}</strong>failed</div>
          <div className="stat"><strong>{backupResult.manifest.duplicate_groups.length}</strong>duplicate groups</div>
        </div>

        <div className="panel">
          <div className="panel-head">Result</div>
          <div className="panel-body">
            <table className="propgrid">
              <tbody>
                <tr><th>Backup directory</th><td className="mono">{backupDir}</td></tr>
                <tr>
                  <th>Verification</th>
                  <td>
                    {failed === 0
                      ? <span className="badge verified">all {fmtCount(verified)} files verified</span>
                      : <span className="badge failed">{fmtCount(failed)} file(s) failed</span>}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {failed > 0 && (
          <div className="panel">
            <div className="panel-head">Failed Files</div>
            <div className="panel-body flush scroll-y">
              <table className="grid">
                <thead><tr><th>Path</th><th>Error</th></tr></thead>
                <tbody>
                  {entries.filter((e) => e.verification_status !== "verified").map((e) => (
                    <tr key={e.source_path}>
                      <td className="mono">{e.source_path}</td>
                      <td className="dim">{e.error}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="panel">
          <div className="panel-head">Report</div>
          <div className="panel-body flush">
            <pre className="report" style={{ border: "none" }}>{backupResult.manifest.report_txt}</pre>
          </div>
        </div>

        <div className="notice info">
          <span>
            Deletion is a separate, explicitly-authorized step. Nothing is removed from the
            device unless you go to <strong>Cleanup</strong> and confirm there.
          </span>
        </div>

        <div className="wizard-footer">
          <span className="spacer" />
          <Link to="/cleanup"><button>Go to Cleanup...</button></Link>
        </div>
      </>
    );
  }

  /* -------------------------------------------------------------- review */

  if (step === "review") {
    return (
      <>
        <div className="page-head">
          <h1>Confirm Backup</h1>
          <p className="page-sub">Review the selection before copying.</p>
        </div>

        {error && <div className="notice error"><span><strong>Error.</strong> {error}</span></div>}

        <div className="notice info">
          <span>Nothing is copied until you press <strong>Start Backup</strong>.</span>
        </div>

        <div className="panel">
          <div className="panel-head">Summary</div>
          <div className="panel-body">
            <table className="propgrid">
              <tbody>
                <tr><th>Files selected</th><td>{fmtCount(totals.includedCount)}</td></tr>
                <tr><th>Total size</th><td>{fmtSize(totals.includedSize)}</td></tr>
                <tr><th>Excluded</th><td className="dim">{fmtCount(totals.excludedCount)} files ({fmtSize(totals.excludedSize)})</td></tr>
                <tr><th>Device</th><td className="mono">{discovery.device_serial}</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">Destination</div>
          <div className="panel-body">
            <div className="field">
              <label htmlFor="dest">Backup destination parent directory</label>
              <input
                id="dest"
                type="text"
                placeholder="~/Desktop  (default)"
                value={destParent}
                onChange={(e) => setDestParent(e.target.value)}
              />
              <div className="hint">A timestamped subfolder is created inside this directory.</div>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">Included Categories</div>
          <div className="panel-body flush scroll-y">
            <table className="grid">
              <thead><tr><th>Category</th><th className="right">Files</th><th className="right">Size</th></tr></thead>
              <tbody>
                {discovery.categories.map((cat) => {
                  const s = categoryStats(cat, states);
                  if (s.includedCount === 0) return null;
                  return (
                    <tr key={cat.id}>
                      <td>{cat.label}</td>
                      <td className="right">{fmtCount(s.includedCount)}</td>
                      <td className="right">{fmtSize(s.includedSize)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">Excluded</div>
          <div className="panel-body flush scroll-y">
            <table className="grid">
              <thead><tr><th>Category</th><th className="right">Excluded files</th></tr></thead>
              <tbody>
                {discovery.categories.map((cat) => {
                  const s = categoryStats(cat, states);
                  const excluded = s.total - s.includedCount;
                  if (excluded === 0) return null;
                  return (
                    <tr key={cat.id}>
                      <td>{cat.label}</td>
                      <td className="right">{fmtCount(excluded)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {discovery.inaccessible.length > 0 && (
          <div className="panel">
            <div className="panel-head">Inaccessible Locations</div>
            <div className="panel-body">
              {discovery.inaccessible.map((i) => (
                <div key={i.path} style={{ marginBottom: 6 }}>
                  <div className="mono">{i.path}</div>
                  <div className="dim">{i.reason}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="wizard-footer">
          <span className="dim">{fmtCount(totals.includedCount)} files, {fmtSize(totals.includedSize)}</span>
          <span className="spacer" />
          <button onClick={() => setStep("select")}>&lt; Back</button>
          <button className="primary" onClick={doStartBackup}>Start Backup</button>
        </div>
      </>
    );
  }

  /* -------------------------------------------------------------- select */

  return (
    <>
      <div className="page-head">
        <h1>Select Files</h1>
        <p className="page-sub">Choose what to copy off the device.</p>
        <span className="spacer" />
        <span className="dim">
          {discovery.categories.length} categories · {fmtCount(totalFiles)} files
        </span>
      </div>

      {error && <div className="notice error"><span><strong>Error.</strong> {error}</span></div>}

      <div className="toolbar">
        <span className="toolbar-label">Filter:</span>
        <input
          type="text"
          placeholder="Filter by filename..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <button onClick={() => setFilter("")} disabled={!filter}>Clear</button>
        <span className="sep" />
        <button onClick={() => setAll("INCLUDE")}>Select All</button>
        <button onClick={() => setAll("EXCLUDE")}>Deselect All</button>
        <span className="sep" />
        <button onClick={expandAll} disabled={!!needle}>Expand All</button>
        <button onClick={collapseAll} disabled={!!needle}>Collapse All</button>
      </div>

      <FileTree
        roots={displayRoots}
        states={states}
        onSetFiles={setFilesState}
        expanded={effectiveExpanded}
        onToggleExpand={(key) => setExpanded((p) => ({ ...p, [key]: !p[key] }))}
        fmtSize={fmtSize}
        emptyLabel={needle ? `No files match "${filter}".` : "No files discovered."}
      />

      <div className="statstrip" style={{ borderTop: "none", borderRadius: "0 0 var(--r) var(--r)" }}>
        <div className="stat"><strong>{fmtCount(totals.includedCount)}</strong>selected</div>
        <div className="stat"><strong>{fmtSize(totals.includedSize)}</strong>to copy</div>
        <div className="stat"><strong>{fmtCount(totals.excludedCount)}</strong>excluded</div>
        {discovery.inaccessible.length > 0 && (
          <div className="stat dim">{discovery.inaccessible.length} inaccessible location(s)</div>
        )}
      </div>

      <div className="wizard-footer">
        <span className="dim">Select files, then continue.</span>
        <span className="spacer" />
        <button
          className="primary"
          onClick={doReview}
          disabled={totals.includedCount === 0}
        >
          Next &gt;
        </button>
      </div>
    </>
  );
}
