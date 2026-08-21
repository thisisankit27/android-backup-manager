const BASE = "/api";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export interface DeviceInfo {
  serial: string;
  manufacturer: string;
  model: string;
  android_version: string;
  sdk: number;
  storage_total_bytes: number | null;
  storage_used_bytes: number | null;
  storage_free_bytes: number | null;
}

export interface DeviceStatus {
  connected: boolean;
  reason?: string;
  device?: DeviceInfo;
  last_backup?: any;
  last_deletion_preview?: any;
  last_deletion?: any;
}

export interface DiscoveredFile {
  path: string;
  size: number;
  mtime: number;
  sha256: string;
  category_id: string;
  filename: string;
  extension: string;
  is_trashed: boolean;
  crypt14_kind: "current" | "historical" | null;
  default_state: "INCLUDE" | "EXCLUDE" | "INACCESSIBLE";
}

export interface Category {
  id: string;
  label: string;
  remote_dir: string;
  report_group: string;
  default_include: boolean;
  files: DiscoveredFile[];
}

export interface DiscoveryResult {
  device_serial: string;
  generated_at: string;
  categories: Category[];
  inaccessible: { path: string; reason: string }[];
}

export interface JobStatus {
  id: string;
  kind: string;
  status: "running" | "done" | "error";
  events: any[];
  next_index: number;
  result: any;
  error: string | null;
}

export const api = {
  deviceStatus: () => req<DeviceStatus>("/device/status"),
  startDiscovery: () => req<{ job_id: string }>("/discovery/start", { method: "POST" }),
  getDiscovery: (id: string) => req<DiscoveryResult>(`/discovery/${id}`),
  freezeSelection: (discovery_id: string, overrides: Record<string, string>) =>
    req<{ selection_id: string; included_files: number; included_size: number; excluded_files: number }>(
      "/selection/freeze",
      { method: "POST", body: JSON.stringify({ discovery_id, overrides }) }
    ),
  getSelection: (id: string) => req<any>(`/selection/${id}`),
  startBackup: (selection_id: string, dest_parent?: string) =>
    req<{ job_id: string; backup_dir: string }>("/backup/start", {
      method: "POST",
      body: JSON.stringify({ selection_id, dest_parent }),
    }),
  getManifest: (backup_dir: string) =>
    req<any>(`/backup/manifest?backup_dir=${encodeURIComponent(backup_dir)}`),
  startDeletionPreview: (backup_dir: string) =>
    req<{ job_id: string }>("/deletion/preview/start", {
      method: "POST",
      body: JSON.stringify({ backup_dir }),
    }),
  getPreview: (backup_dir: string, preview_id: string) =>
    req<any>(`/deletion/preview?backup_dir=${encodeURIComponent(backup_dir)}&preview_id=${preview_id}`),
  executeDeletion: (payload: {
    backup_dir: string;
    preview_id: string;
    confirmation_phrase: string;
    preview_acknowledged: boolean;
    dry_run?: boolean;
  }) => req<{ job_id: string }>("/deletion/execute", { method: "POST", body: JSON.stringify(payload) }),
  history: () => req<any[]>("/history"),
  getConfig: () => req<any>("/config"),
  updateConfig: (payload: any) => req<any>("/config", { method: "PUT", body: JSON.stringify(payload) }),
  getJob: (id: string, since = 0) => req<JobStatus>(`/jobs/${id}?since=${since}`),
};

export function watchJob(
  jobId: string,
  onEvent: (event: any) => void,
  onFinal: (status: "done" | "error", result: any, error: string | null) => void
): () => void {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${window.location.host}${BASE}/ws/jobs/${jobId}`);
  ws.onmessage = (msg) => {
    const payload = JSON.parse(msg.data);
    if (payload.type === "event") onEvent(payload.data);
    else if (payload.type === "final") onFinal(payload.status, payload.result, payload.error);
  };
  return () => ws.close();
}
