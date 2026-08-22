import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api, DeviceStatus } from "../api/client";

interface DeviceContextValue {
  status: DeviceStatus | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

const DeviceContext = createContext<DeviceContextValue>({
  status: null,
  loading: false,
  error: null,
  refresh: () => {},
});

/** Single shared device-status fetch. Deliberately NOT polled: every call
 * shells out to adb on the connected phone, so it refreshes on mount and
 * whenever something explicitly asks (the Dashboard/status bar Refresh). */
export function DeviceProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<DeviceStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .deviceStatus()
      .then(setStatus)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(refresh, [refresh]);

  return (
    <DeviceContext.Provider value={{ status, loading, error, refresh }}>
      {children}
    </DeviceContext.Provider>
  );
}

export function useDevice() {
  return useContext(DeviceContext);
}
