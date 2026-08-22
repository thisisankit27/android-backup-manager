import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState, IconClock } from "../components/EmptyState";
import { fmtCount, fmtSize } from "../lib/format";

const TYPE_LABELS: Record<string, string> = {
  discovery: "Discovery",
  selection: "Selection",
  backup: "Backup",
  deletion_preview: "Deletion Preview",
  deletion: "Deletion",
};

function details(e: any): string {
  switch (e.type) {
    case "discovery": return `${e.categories} categories, ${fmtCount(e.files)} files`;
    case "selection": return `${fmtCount(e.included_files)} files selected, ${fmtSize(e.included_size)}`;
    case "backup": return `${e.verified}/${e.files} verified — ${e.backup_dir}`;
    case "deletion_preview": return `${e.eligible} eligible, ${e.skipped} skipped — ${e.backup_dir}`;
    case "deletion": return `${e.deleted} deleted, ${e.skipped} skipped${e.aborted_reason ? " (ABORTED)" : ""}`;
    default: return "";
  }
}

export default function History() {
  const [events, setEvents] = useState<any[] | null>(null);
  const [typeFilter, setTypeFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    api.history().then(setEvents).catch((e) => setError(e.message));
  };

  useEffect(load, []);

  const shown = useMemo(
    () => (events || []).filter((e) => !typeFilter || e.type === typeFilter),
    [events, typeFilter]
  );

  return (
    <>
      <div className="page-head">
        <h1>History</h1>
        <p className="page-sub">Every operation this tool has run, oldest audit record kept on disk.</p>
      </div>

      {error && <div className="notice error"><span><strong>Error.</strong> {error}</span></div>}

      <div className="toolbar">
        <span className="toolbar-label">Type:</span>
        <select
          style={{ width: 180 }}
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="">(all)</option>
          {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <span className="sep" />
        <button onClick={load}>Refresh</button>
        <span className="spacer" />
        <span className="toolbar-label">{fmtCount(shown.length)} record(s)</span>
      </div>

      <div className="panel">
        <div className="panel-body flush" style={{ maxHeight: 460, overflow: "auto" }}>
          {events !== null && shown.length === 0 ? (
            <EmptyState
              icon={IconClock}
              title={typeFilter ? "No records of that type" : "Nothing has happened yet"}
              actions={
                typeFilter ? (
                  <button onClick={() => setTypeFilter("")}>Show everything</button>
                ) : (
                  <Link to="/discover"><button className="primary">Scan the device</button></Link>
                )
              }
            >
              {typeFilter
                ? "Every other kind of record is still here — clear the filter to see them."
                : "Every scan, backup and deletion this tool runs is written down here, so you can always check what happened and when."}
            </EmptyState>
          ) : (
          <table className="grid">
            <thead>
              <tr><th>When</th><th>Type</th><th>Device</th><th>Details</th></tr>
            </thead>
            <tbody>
              {shown.map((e, i) => (
                <tr key={i}>
                  <td className="mono">{e.timestamp}</td>
                  <td>{TYPE_LABELS[e.type] || e.type}</td>
                  <td className="mono">{e.device_serial}</td>
                  <td className="dim">{details(e)}</td>
                </tr>
              ))}
              {events === null && !error && (
                <tr><td colSpan={4} className="dim" style={{ padding: 16, textAlign: "center" }}>
                  Loading...
                </td></tr>
              )}
            </tbody>
          </table>
          )}
        </div>
      </div>
    </>
  );
}
