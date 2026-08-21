import { useEffect, useState } from "react";
import { api } from "../api/client";

const TYPE_LABELS: Record<string, string> = {
  discovery: "Discovery",
  selection: "Selection",
  backup: "Backup",
  deletion_preview: "Deletion Preview",
  deletion: "Deletion",
};

export default function History() {
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => { api.history().then(setEvents); }, []);

  return (
    <>
      <h2>History</h2>
      <p className="subtitle">Every discovery, backup, verification, and deletion this app has ever run.</p>
      <div className="card">
        <table>
          <thead><tr><th>When</th><th>Type</th><th>Device</th><th>Details</th></tr></thead>
          <tbody>
            {events.map((e, i) => (
              <tr key={i}>
                <td className="dim">{e.timestamp}</td>
                <td>{TYPE_LABELS[e.type] || e.type}</td>
                <td className="mono">{e.device_serial}</td>
                <td className="dim">
                  {e.type === "discovery" && `${e.categories} categories, ${e.files} files`}
                  {e.type === "selection" && `${e.included_files} files selected, ${e.included_size} bytes`}
                  {e.type === "backup" && `${e.verified}/${e.files} verified — ${e.backup_dir}`}
                  {e.type === "deletion_preview" && `${e.eligible} eligible, ${e.skipped} skipped — ${e.backup_dir}`}
                  {e.type === "deletion" && `${e.deleted} deleted, ${e.skipped} skipped${e.aborted_reason ? " (ABORTED)" : ""}`}
                </td>
              </tr>
            ))}
            {events.length === 0 && <tr><td colSpan={4} className="dim">No activity yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
