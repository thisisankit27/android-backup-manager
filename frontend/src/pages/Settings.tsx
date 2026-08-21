import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function Settings() {
  const [config, setConfig] = useState<any>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.getConfig().then(setConfig); }, []);

  if (!config) return <p>Loading...</p>;

  const save = async () => {
    const updated = await api.updateConfig({
      default_backup_parent: config.default_backup_parent,
      default_excluded_report_groups: config.default_excluded_report_groups,
      protected_filename_patterns: config.protected_filename_patterns,
    });
    setConfig(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <>
      <h2>Settings</h2>
      <p className="subtitle">
        These are defaults only. They cannot weaken the mandatory manifest-driven deletion
        safety checks — every deletion still requires fresh hash verification and explicit
        confirmation regardless of these settings.
      </p>
      <div className="card">
        <label className="dim">Default backup destination parent</label>
        <input type="text" value={config.default_backup_parent}
               onChange={(e) => setConfig({ ...config, default_backup_parent: e.target.value })} />

        <label className="dim" style={{ marginTop: 16, display: "block" }}>
          Report groups excluded by default (comma-separated)
        </label>
        <input type="text" value={config.default_excluded_report_groups.join(", ")}
               onChange={(e) => setConfig({ ...config, default_excluded_report_groups: e.target.value.split(",").map((s: string) => s.trim()).filter(Boolean) })} />

        <label className="dim" style={{ marginTop: 16, display: "block" }}>
          Protected filenames — always excluded from deletion (comma-separated)
        </label>
        <input type="text" value={config.protected_filename_patterns.join(", ")}
               onChange={(e) => setConfig({ ...config, protected_filename_patterns: e.target.value.split(",").map((s: string) => s.trim()).filter(Boolean) })} />

        <div style={{ marginTop: 20 }}>
          <button className="primary" onClick={save}>Save</button>
          {saved && <span style={{ marginLeft: 12 }} className="badge verified">Saved</span>}
        </div>
      </div>
    </>
  );
}
