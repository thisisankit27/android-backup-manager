import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { AdbStatus, api, DeviceStatus } from "../api/client";

interface DeviceContextValue {
  status: DeviceStatus | null;
  adb: AdbStatus | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

const DeviceContext = createContext<DeviceContextValue>({
  status: null,
  adb: null,
  loading: false,
  error: null,
  refresh: () => {},
});

/** Single shared device-status fetch. Deliberately NOT polled: every call
 * shells out to adb on the connected phone, so it refreshes on mount and
 * whenever something explicitly asks (the Dashboard/status bar Refresh).
 *
 * adb availability is fetched first and separately, because when adb is
 * missing the device endpoint can't answer anything useful — and "adb is
 * missing" is a different problem from "no phone plugged in", which the UI
 * has to be able to tell apart. */
export function DeviceProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<DeviceStatus | null>(null);
  const [adb, setAdb] = useState<AdbStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .adbStatus()
      .then((a) => {
        setAdb(a);
        // No point asking about a device when nothing can talk to one.
        if (!a.found) {
          setStatus(null);
          return null;
        }
        return api.deviceStatus().then(setStatus);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(refresh, [refresh]);

  return (
    <DeviceContext.Provider value={{ status, adb, loading, error, refresh }}>
      {children}
    </DeviceContext.Provider>
  );
}

export function useDevice() {
  return useContext(DeviceContext);
}
