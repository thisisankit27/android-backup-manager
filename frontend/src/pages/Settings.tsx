import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function Settings() {
  const [config, setConfig] = useState<any>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getConfig().then(setConfig).catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <>
        <div className="page-head"><h1>Options</h1></div>
        <div className="notice error"><span><strong>Error.</strong> {error}</span></div>
      </>
    );
  }

  if (!config) {
    return (
      <>
        <div className="page-head"><h1>Options</h1></div>
        <div className="placeholder">Loading...</div>
      </>
    );
  }

  const save = async () => {
    setError(null);
    try {
      const updated = await api.updateConfig({
        default_backup_parent: config.default_backup_parent,
        default_excluded_report_groups: config.default_excluded_report_groups,
        protected_filename_patterns: config.protected_filename_patterns,
      });
      setConfig(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const listField = (key: string) => ({
    value: (config[key] as string[]).join(", "),
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      setConfig({
        ...config,
        [key]: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
      }),
  });

  return (
    <>
      <div className="page-head">
        <h1>Options</h1>
        <p className="page-sub">Defaults for new operations.</p>
      </div>

      <div className="notice warn">
        <span>
          These are <strong>defaults only</strong>. They cannot weaken the mandatory deletion
          safety checks — every deletion still requires fresh hash verification and explicit
          confirmation regardless of what is set here.
        </span>
      </div>

      <div className="panel">
        <div className="panel-head">Backup</div>
        <div className="panel-body">
          <div className="field">
            <label htmlFor="destparent">Default backup destination parent</label>
            <input
              id="destparent"
              type="text"
              value={config.default_backup_parent}
              onChange={(e) => setConfig({ ...config, default_backup_parent: e.target.value })}
            />
            <div className="hint">Timestamped backup folders are created inside this directory.</div>
          </div>

          <div className="field">
            <label htmlFor="excluded">Report groups excluded by default</label>
            <input id="excluded" type="text" {...listField("default_excluded_report_groups")} />
            <div className="hint">Comma-separated. Categories in these groups start unchecked.</div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">Deletion Safety</div>
        <div className="panel-body">
          <div className="field">
            <label htmlFor="protected">Protected filenames — never eligible for deletion</label>
            <input id="protected" type="text" {...listField("protected_filename_patterns")} />
            <div className="hint">
              Comma-separated. Matching files are always skipped by the deletion executor.
            </div>
          </div>
        </div>
      </div>

      <div className="wizard-footer">
        {saved && <span className="badge verified">Saved</span>}
        <span className="spacer" />
        <button className="primary" onClick={save}>Apply</button>
      </div>
    </>
  );
}
