import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { UpdateOutcome, UpdateState, api, watchJob } from "../api/client";

export interface InstallProgress {
  phase: "checksums" | "downloading" | "downloaded" | "verifying" | "verified" | "installing";
  downloaded?: number;
  total?: number | null;
}

interface UpdateContextValue {
  state: UpdateState | null;
  busy: boolean;
  /** Re-runs the check. `force` skips the once-a-day cache. */
  refresh: (force?: boolean) => Promise<void>;
  setEnabled: (enabled: boolean) => Promise<void>;
  dismiss: () => Promise<void>;

  installing: boolean;
  progress: InstallProgress | null;
  outcome: UpdateOutcome | null;
  installError: string | null;
  install: () => Promise<void>;
  restart: () => Promise<void>;
}

const UpdateContext = createContext<UpdateContextValue>({
  state: null,
  busy: false,
  refresh: async () => {},
  setEnabled: async () => {},
  dismiss: async () => {},
  installing: false,
  progress: null,
  outcome: null,
  installError: null,
  install: async () => {},
  restart: async () => {},
});

export function UpdateProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<UpdateState | null>(null);
  const [busy, setBusy] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [progress, setProgress] = useState<InstallProgress | null>(null);
  const [outcome, setOutcome] = useState<UpdateOutcome | null>(null);
  const [installError, setInstallError] = useState<string | null>(null);

  // Backed by a single provider mounted in the shell so the banner and the
  // Options toggle can never disagree about whether checking is on.
  const refresh = useCallback(async (force = false) => {
    setBusy(true);
    try {
      setState(await api.updateCheck(force));
    } catch {
      // The check is a courtesy. Nothing about the app stops working when
      // it fails, so it fails without saying anything.
    } finally {
      setBusy(false);
    }
  }, []);

  const setEnabled = useCallback(async (enabled: boolean) => {
    setBusy(true);
    try {
      setState(await api.setUpdatePreference(enabled));
    } finally {
      setBusy(false);
    }
  }, []);

  const dismiss = useCallback(async () => {
    if (!state?.latest) return;
    setState(await api.dismissUpdate(state.latest.version));
  }, [state]);

  const install = useCallback(async () => {
    // Clearing first: a failed attempt's error must not still be on screen
    // while the next one is downloading.
    setInstallError(null);
    setOutcome(null);
    setProgress(null);
    setInstalling(true);
    try {
      const { job_id } = await api.installUpdate();
      watchJob(
        job_id,
        (event) => setProgress(event),
        (status, result, error) => {
          setInstalling(false);
          setProgress(null);
          if (status === "done") setOutcome(result);
          else setInstallError(error || "The update failed.");
        }
      );
    } catch (e: any) {
      setInstalling(false);
      setInstallError(e.message);
    }
  }, []);

  const restart = useCallback(async () => {
    try {
      await api.restartApp();
    } catch (e: any) {
      setInstallError(e.message);
    }
  }, []);

  // Once, on launch. Not polled: a new release does not appear mid-session
  // often enough to justify asking about it repeatedly.
  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <UpdateContext.Provider
      value={{
        state,
        busy,
        refresh,
        setEnabled,
        dismiss,
        installing,
        progress,
        outcome,
        installError,
        install,
        restart,
      }}
    >
      {children}
    </UpdateContext.Provider>
  );
}

export function useUpdate() {
  return useContext(UpdateContext);
}
