import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useUpdate } from "../state/update";

function UpdatesPanel() {
  const { state, busy, refresh, setEnabled } = useUpdate();
  if (!state) return null;

  const lastChecked =
    state.checked_at != null ? new Date(state.checked_at * 1000).toLocaleString() : "never";

  return (
    <div className="panel">
      <div className="panel-head">Updates</div>
      <div className="panel-body">
        <table className="propgrid">
          <tbody>
            <tr>
              <th>Installed version</th>
              <td className="mono">
                {state.current_version}
                {!state.is_release_build && (
                  <span className="dim"> — source checkout, not updatable</span>
                )}
              </td>
            </tr>
            <tr>
              <th>Last checked</th>
              <td>
                {state.enabled ? lastChecked : <span className="dim">checking is off</span>}
              </td>
            </tr>
            {state.enabled && state.latest && (
              <tr>
                <th>Latest release</th>
                <td className="mono">{state.latest.version}</td>
              </tr>
            )}
            {state.enabled && state.error && (
              <tr>
                <th>Result</th>
                <td className="dim">could not reach GitHub — {state.error}</td>
              </tr>
            )}
            {!state.supported && (
              <tr>
                <th>Availability</th>
                <td className="dim">no installer is published for this platform</td>
              </tr>
            )}
          </tbody>
        </table>

        <div className="check-row" style={{ marginTop: "var(--sp-3)" }}>
          <input
            id="updatecheck"
            type="checkbox"
            checked={state.enabled}
            disabled={busy}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          <label htmlFor="updatecheck">
            Check GitHub for a new version once a day
            <div className="hint">
              The only network request this app makes. It asks GitHub what the latest
              release is and sends nothing about you, your device or your files. Turn
              this off and the app never contacts anything.
            </div>
          </label>
        </div>

        <div className="toolbar">
          <button onClick={() => refresh(true)} disabled={busy || !state.enabled}>
            {busy ? "Checking..." : "Check now"}
          </button>
          <span className="spacer" />
          <a className="button-link" href={state.releases_url} target="_blank" rel="noreferrer">
            All releases
          </a>
        </div>
      </div>
    </div>
  );
}

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

      <UpdatesPanel />

      <div className="wizard-footer">
        {saved && <span className="badge verified">Saved</span>}
        <span className="spacer" />
        <button className="primary" onClick={save}>Apply</button>
      </div>
    </>
  );
}
