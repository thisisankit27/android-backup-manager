import { useState } from "react";
import { fmtSize } from "../lib/format";
import { InstallProgress, useUpdate } from "../state/update";

const PHASE_LABEL: Record<InstallProgress["phase"], string> = {
  checksums: "Fetching checksums...",
  downloading: "Downloading",
  downloaded: "Downloaded",
  verifying: "Verifying...",
  verified: "Verified",
  installing: "Installing...",
};

function progressText(progress: InstallProgress): string {
  if (progress.phase !== "downloading") return PHASE_LABEL[progress.phase];
  const done = fmtSize(progress.downloaded ?? 0);
  return progress.total ? `Downloading ${done} of ${fmtSize(progress.total)}` : `Downloading ${done}`;
}

/**
 * The strip under the title bar that either asks for permission to check
 * for updates, or announces one that was found and installs it.
 *
 * An information bar rather than a dialog or a toast, on purpose: it must
 * be impossible for this to appear over a running backup and swallow a
 * click meant for something else. When there is nothing to say it renders
 * nothing at all and the layout is unchanged.
 */
export default function UpdateBanner() {
  const {
    state,
    busy,
    setEnabled,
    dismiss,
    installing,
    progress,
    outcome,
    installError,
    install,
    restart,
  } = useUpdate();
  const [showNotes, setShowNotes] = useState(false);

  if (!state) return null;

  // First launch: no check has run and none will until this is answered.
  if (!state.asked) {
    return (
      <div className="infobar">
        <span className="infobar-icon" aria-hidden="true">?</span>
        <span className="infobar-text">
          Check GitHub once a day for a new version? This is the only thing this app
          ever sends over the network — your files and device never leave this machine
          either way.
        </span>
        <button onClick={() => setEnabled(true)} disabled={busy}>Yes, check</button>
        <button onClick={() => setEnabled(false)} disabled={busy}>No</button>
      </div>
    );
  }

  // An update that has been applied stays on screen regardless of whether
  // the banner would otherwise still be showing — the user needs to see
  // what happened, especially the restart.
  if (outcome) {
    return (
      <div className="infobar update">
        <span className="infobar-icon" aria-hidden="true">✓</span>
        <span className="infobar-text">{outcome.message}</span>
        {outcome.action === "restart_required" && (
          <button className="primary" onClick={restart}>Restart now</button>
        )}
        {outcome.command && <pre className="infobar-notes">{outcome.command}</pre>}
      </div>
    );
  }

  if (!state.available || state.dismissed || !state.latest) return null;

  const { latest } = state;
  const canInstall = state.is_release_build && !!latest.asset;

  return (
    <div className="infobar update">
      <span className="infobar-icon" aria-hidden="true">↑</span>
      <span className="infobar-text">
        {installing && progress ? (
          <>
            <strong>{progressText(progress)}</strong>
            <span className="dim"> — version {latest.version}</span>
          </>
        ) : installing ? (
          <strong>Starting...</strong>
        ) : (
          <>
            <strong>Version {latest.version}</strong> is available. You have{" "}
            {state.current_version}.
          </>
        )}
      </span>

      {!installing && canInstall && (
        <button className="primary" onClick={install}>Install update</button>
      )}
      {!installing && latest.notes && (
        <button onClick={() => setShowNotes((v) => !v)} aria-expanded={showNotes}>
          {showNotes ? "Hide changes" : "What's changed"}
        </button>
      )}
      {!installing && (
        <a className="button-link" href={latest.html_url} target="_blank" rel="noreferrer">
          Release page
        </a>
      )}
      {!installing && (
        <button onClick={dismiss} disabled={busy}>Later</button>
      )}

      {installing && progress?.phase === "downloading" && progress.total ? (
        <span className="infobar-progress" aria-hidden="true">
          <span style={{ width: `${((progress.downloaded ?? 0) / progress.total) * 100}%` }} />
        </span>
      ) : null}

      {installError && (
        <span className="infobar-error">
          {installError}{" "}
          <a href={latest.html_url} target="_blank" rel="noreferrer">Download it manually</a>
        </span>
      )}

      {showNotes && <pre className="infobar-notes">{latest.notes.trim()}</pre>}
    </div>
  );
}
