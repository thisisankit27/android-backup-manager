import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { UpdateState, api } from "../api/client";

interface UpdateContextValue {
  state: UpdateState | null;
  busy: boolean;
  /** Re-runs the check. `force` skips the once-a-day cache. */
  refresh: (force?: boolean) => Promise<void>;
  setEnabled: (enabled: boolean) => Promise<void>;
  dismiss: () => Promise<void>;
}

const UpdateContext = createContext<UpdateContextValue>({
  state: null,
  busy: false,
  refresh: async () => {},
  setEnabled: async () => {},
  dismiss: async () => {},
});

export function UpdateProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<UpdateState | null>(null);
  const [busy, setBusy] = useState(false);

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

  // Once, on launch. Not polled: a new release does not appear mid-session
  // often enough to justify asking about it repeatedly.
  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <UpdateContext.Provider value={{ state, busy, refresh, setEnabled, dismiss }}>
      {children}
    </UpdateContext.Provider>
  );
}

export function useUpdate() {
  return useContext(UpdateContext);
}
