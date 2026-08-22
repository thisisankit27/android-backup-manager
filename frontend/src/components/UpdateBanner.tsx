import { useState } from "react";
import { useUpdate } from "../state/update";

/**
 * The strip under the title bar that either asks for permission to check
 * for updates, or announces one that was found.
 *
 * An information bar rather than a dialog or a toast, on purpose: it must
 * be impossible for this to appear over a running backup and swallow a
 * click meant for something else. When there is nothing to say it renders
 * nothing at all and the layout is unchanged.
 */
export default function UpdateBanner() {
  const { state, busy, setEnabled, dismiss } = useUpdate();
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

  if (!state.available || state.dismissed || !state.latest) return null;

  const { latest } = state;

  return (
    <div className="infobar update">
      <span className="infobar-icon" aria-hidden="true">↑</span>
      <span className="infobar-text">
        <strong>Version {latest.version}</strong> is available. You have {state.current_version}.
      </span>
      {latest.notes && (
        <button onClick={() => setShowNotes((v) => !v)} aria-expanded={showNotes}>
          {showNotes ? "Hide changes" : "What's changed"}
        </button>
      )}
      <a className="button-link" href={latest.html_url} target="_blank" rel="noreferrer">
        Release page
      </a>
      <button onClick={dismiss} disabled={busy}>Later</button>

      {showNotes && <pre className="infobar-notes">{latest.notes.trim()}</pre>}
    </div>
  );
}
