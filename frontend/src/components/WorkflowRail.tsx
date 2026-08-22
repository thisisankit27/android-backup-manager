import { useLocation, useNavigate } from "react-router-dom";
import { fmtCount } from "../lib/format";
import { useDevice } from "../state/device";
import { getLastDiscoveryId } from "../state/discovery";

/**
 * The four things this app does, in the order they have to happen.
 *
 * These are not four independent pages that happen to share a sidebar.
 * You cannot back up what you have not discovered, and you must not free
 * space without a verified backup to check the device against. That
 * dependency was previously invisible — a flat nav list implied you could
 * start anywhere, and Cleanup in particular would simply sit there empty
 * with no explanation of what was missing.
 *
 * So each step carries its own state, and a blocked step says what is
 * blocking it rather than silently refusing to do anything.
 */
type State = "done" | "active" | "ready" | "locked";

interface Step {
  to: string;
  title: string;
  state: State;
  /** One line under the title: what happened, or what is missing. */
  sub: string;
}

function Mark({ state, n }: { state: State; n: number }) {
  if (state === "done") {
    return (
      <span className="rail-mark" aria-hidden="true">
        <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
          <path d="M2.5 6.2l2.3 2.3 4.7-5" stroke="currentColor" strokeWidth="1.8"
                strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  if (state === "locked") {
    return (
      <span className="rail-mark" aria-hidden="true">
        <svg width="10" height="10" viewBox="0 0 12 12" fill="currentColor">
          <path d="M3.4 5V3.8a2.6 2.6 0 015.2 0V5h.4a.9.9 0 01.9.9v4a.9.9 0 01-.9.9H3a.9.9 0 01-.9-.9v-4A.9.9 0 013 5h.4zm1.3 0h2.6V3.8a1.3 1.3 0 00-2.6 0V5z" />
        </svg>
      </span>
    );
  }
  return <span className="rail-mark" aria-hidden="true">{n}</span>;
}

export default function WorkflowRail() {
  const { status } = useDevice();
  const location = useLocation();
  const navigate = useNavigate();

  const connected = !!status?.connected;
  const device = status?.device;
  // Read on every render rather than held in state: the only thing that
  // writes it is a discovery finishing, which navigates immediately after,
  // and a re-render is guaranteed by that navigation.
  const discoveryId = getLastDiscoveryId();
  const lastBackup = status?.last_backup;
  const lastDeletion = status?.last_deletion;

  const at = (path: string) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);

  const resolve = (path: string, done: boolean, blocked: string | null): State => {
    if (at(path)) return "active";
    if (done) return "done";
    return blocked ? "locked" : "ready";
  };

  const steps: Step[] = [
    {
      to: "/",
      title: "Connect",
      state: resolve("/", connected, null),
      sub: connected && device ? `${device.manufacturer} ${device.model}` : "no device",
    },
    {
      to: "/discover",
      title: "Discover",
      state: resolve("/discover", !!discoveryId, connected ? null : "connect"),
      // A completed scan stays completed even if the phone is now
      // unplugged -- saying "connect a phone first" under a green tick
      // reads as a contradiction.
      sub: discoveryId ? "scan complete" : connected ? "read-only scan" : "connect a phone first",
    },
    {
      to: "/backup",
      title: "Back Up",
      state: resolve("/backup", !!lastBackup, discoveryId ? null : "discover"),
      sub: lastBackup
        ? `${fmtCount(lastBackup.verified)} verified`
        : discoveryId
        ? "ready to select"
        : "discover first",
    },
    {
      to: "/cleanup",
      title: "Free Space",
      state: resolve("/cleanup", !!lastDeletion, lastBackup ? null : "backup"),
      sub: lastDeletion
        ? `${fmtCount(lastDeletion.deleted)} deleted`
        : lastBackup
        ? "ready to review"
        : "needs a verified backup",
    },
  ];

  return (
    <nav className="rail" aria-label="Workflow">
      {steps.map((step, i) => (
        <button
          key={step.to}
          className={`rail-step ${step.state}`}
          onClick={() => navigate(step.to)}
          disabled={step.state === "locked"}
          aria-current={step.state === "active" ? "step" : undefined}
          title={step.state === "locked" ? `${step.title} — ${step.sub}` : undefined}
        >
          <Mark state={step.state} n={i + 1} />
          <span className="rail-text">
            <span className="rail-title">{step.title}</span>
            <span className="rail-sub">{step.sub}</span>
          </span>
        </button>
      ))}
    </nav>
  );
}
