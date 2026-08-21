# Android Backup Manager

A local, safety-critical web application for backing up personal files off an
Android phone via ADB, verifying every copy with SHA-256, and — as a
completely separate, explicitly-authorized step — deleting only the exact
files that were verified.

This grew out of a real one-off backup/cleanup session (10,330 files,
10.56 GB, zero data loss) done via a set of CLI scripts. This app is the
reusable, interactive version of that same workflow, so it can be repeated
safely on this phone or another one without hand-writing a new set of
commands each time.

**A successful backup does NOT automatically authorize deletion.** These are
two separate workflows, gated by two separate, explicit user actions.

## What it does

1. Connects to an Android phone over USB via `adb`.
2. **Discovers** accessible personal files read-only (Camera, Screenshots,
   Downloads, Documents, WhatsApp media, and any other user-created folders)
   and reports — without touching — locations it cannot read
   (`Android/data/<package>`).
3. Lets you **interactively include/exclude** whole categories or individual
   files before anything is copied.
4. **Freezes** that decision into an immutable selection manifest, then
   **copies** exactly those files into a timestamped folder on your Desktop.
5. **Verifies** every copy: source SHA-256 == backup SHA-256 and source
   size == backup size, or it isn't marked verified.
6. Writes a **manifest** (JSON + CSV, with its own SHA-256) and human-readable
   reports.
7. Later, on a separate visit to **Cleanup**: re-verifies every backed-up file
   against the device *right now*, produces a **deletion preview**, and only
   deletes a file if you type `DELETE VERIFIED BACKUPS`, tick an
   acknowledgement, and every one of that file's checks still passes at the
   moment of deletion.

## Architecture

```
backend/            FastAPI service, bound to 127.0.0.1 only
  app/adb/           AdbClient interface + RealAdbClient (subprocess) + FakeAdbClient (test sandbox)
  app/discovery/     read-only scanning + classification (Camera/Screenshots/WhatsApp/.../Disposable)
  app/selection/     turns discovery + user choices into a frozen SelectionManifest
  app/backup/        copy + SHA-256 verify pipeline, manifest-driven
  app/manifest/      duplicate detection
  app/deletion/      fresh pre-deletion verification + manifest-driven deletion executor
  app/reports/       human-readable report rendering
  app/audit/         local JSON/CSV persistence + operation history
  app/api/           HTTP + WebSocket routes; owns every safety check
  tests/             pytest suite against a fake sandbox device (no real phone touched)
frontend/           React + TypeScript + Vite SPA
  src/pages/         Dashboard, Discover, Backup, Cleanup, History, Settings
  src/api/client.ts  typed fetch/WebSocket client — the browser never talks to adb directly
```

The backend owns every filesystem/adb operation. The browser can only ask
the backend to do things through a fixed set of endpoints; it cannot run
arbitrary commands or reach the device directly.

### Why an `AdbClient` interface

Business logic (discovery, backup, deletion) is written only against the
`AdbClient` protocol in `app/adb/client.py`. `RealAdbClient` talks to an
actual phone over `adb` using structured subprocess argument lists (never
shell interpolation locally). `FakeAdbClient` operates on a plain local
directory standing in for device storage. This is what lets the entire
destructive deletion path be exhaustively unit-tested — including
connection-loss mid-deletion — without ever touching a real phone.

## Prerequisites

- Python 3.11+
- Node.js 18+
- `adb` (Android Debug Bridge) on your `PATH` — e.g. `sudo apt install
  android-tools-adb` on Debian/Ubuntu, or Google's `platform-tools` zip.

## ADB setup on the phone

1. Settings → About phone → tap **Build number** 7 times to unlock Developer
   Options.
2. Settings → System → Developer options → enable **USB debugging**.
3. Connect via USB, unlock the phone, and accept the **"Allow USB
   debugging?"** prompt (tick "Always allow from this computer" if you don't
   want to re-approve every time).
4. Pull down the USB notification and select **File Transfer** mode (not
   "Charging only").

## Installation

```bash
# backend
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# frontend
cd ../frontend
npm install
```

## Running locally

```bash
# terminal 1 — backend (binds to 127.0.0.1:8420)
cd backend
./.venv/bin/python run.py

# terminal 2 — frontend dev server (binds to 127.0.0.1:5173, proxies /api to the backend)
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`.

## The recommended workflow

1. Connect the Android phone; check **Dashboard** shows `CONNECTED`.
2. **Discover** — read-only scan. Nothing is copied or modified.
3. On the **Backup** page, review categories, expand any of them to include
   or exclude individual files, then click **Review Backup**.
4. Review the summary (included/excluded categories, inaccessible
   locations, backup destination) and click **Start Backup**.
5. Watch live copy + verification progress. Review the backup report
   (per-category counts, failures, duplicate groups).
6. **Stop here.** Deletion is a separate visit to **Cleanup** — it is never
   triggered automatically after a backup.
7. On **Cleanup**, pick the backup directory and click **Run Fresh
   Verification** — this re-checks every file's path and SHA-256 against
   the device *right now*, independent of what the original backup found.
8. Review the **deletion preview**: exact eligible list, exact skip reasons,
   and the WhatsApp `.crypt14` database inventory (current vs historical).
9. Type `DELETE VERIFIED BACKUPS`, tick the acknowledgement, and click
   **Delete Verified Files** (or **Run Dry Run** first to see what would
   happen with nothing deleted).
10. Immediately before each individual file is deleted, its path and hash
    are checked one more time; a mismatch or a lost connection skips it
    (or stops the whole run) rather than deleting it.
11. Review the deletion report and log.

## The verification model

A file is only ever marked `verified` if, at copy time:
`source_size == backup_size` **and** `sha256(source) == sha256(backup)`.
A failed or unverified file can never later become a deletion candidate —
deletion eligibility is only ever computed from manifest rows whose
`verification_status == "verified"`.

## The deletion safety model

Deletion is **manifest-driven, never search-driven**. The deletion preview
only ever looks at the exact rows of one specific backup manifest — it never
performs a new directory listing to "find more things to delete." A file
becomes eligible only if, checked again right now:

1. its exact original path still exists on the device,
2. its current on-device SHA-256 still matches the manifest,
3. its backup file still exists locally,
4. its current backup-file SHA-256 still matches the manifest, and
5. the manifest row itself is complete.

Any ambiguity skips the file — it is never deleted "to be safe." A file
created on the device *after* the backup was made can never appear in a
deletion preview, because the preview only iterates the frozen manifest's
paths, not a live re-scan of the same folder.

Deletion only ever removes individual files via a single-file `rm`. It never
deletes a directory, never uses a wildcard, and never acts on filename,
extension, size, date, or category alone.

If the adb connection is lost partway through a deletion run, the run stops
immediately; everything deleted before that point is logged, and nothing
after it is touched.

### WhatsApp `.crypt14` handling

`.crypt14` (and `.crypt15`) files are inventoried separately from ordinary
media. A filename with an embedded date (e.g.
`msgstore-2026-08-14.1.db.crypt14`) is treated as a **historical** backup
and may be selected for deletion, subject to the same verification as any
other file. A filename without a date (e.g. `msgstore.db.crypt14`,
`msgstore-increment-1.db.crypt14`) is treated as the **current** local
database and is hard-excluded from deletion — both in the preview logic and,
defensively, a second time in the deletion executor itself, which refuses to
delete any file matching a configured protected-filename pattern regardless
of what a preview says.

## Reports and audit logs

Everything about a specific backup lives inside that backup's own
`_audit/` folder, so a backup remains self-contained and portable even after
you clean up the phone:

- `_audit/manifest.json` / `manifest.csv` / `manifest.sha256`
- `_audit/deletion_preview_<id>.json`
- `_audit/deletion_report_<id>.json`

App-level working state (discoveries, selection manifests, the append-only
deletion log, and the cross-backup history index) lives entirely outside any
git repository, under `~/.android-backup-manager/`.

## Testing

```bash
cd backend
./.venv/bin/pytest -q
```

The suite runs entirely against `tests/fixtures/sample_device/` through
`FakeAdbClient` — no real device is touched, per this project's development
rule that the deletion engine must be proven safe on a fake device before it
is ever pointed at a real phone. Coverage includes: category/individual-file
selection, successful copy + verification, a corrupted-transfer case, hash-
based duplicate detection, and the full deletion-safety matrix (changed
source, missing source, missing backup, backup hash drift, incomplete
manifest, failed original verification, protected WhatsApp databases, files
created after backup, and connection loss both during preview and mid-
deletion).

## Security considerations

- The backend binds to `127.0.0.1` only — never `0.0.0.0`.
- CORS is restricted to the local dev server's origin.
- The browser never issues adb commands or filesystem paths directly; every
  action goes through a fixed backend endpoint that re-validates state
  server-side (e.g. the confirmation phrase and acknowledgement for deletion
  are checked in the backend, not just the UI).
- All `adb shell` remote commands are built with `shlex.quote()` around any
  path; all local `subprocess` calls use argument lists, never `shell=True`.
- Logs (`~/.android-backup-manager/state/deletion_log.csv`, history) record
  paths, hashes, and outcomes — never file contents.

## Limitations

- `Android/data/<package>/*` contents cannot be read on Android 11+ due to
  scoped storage, even via `adb shell` — the app reports these folders by
  name only and never implies they were backed up.
- Only one connected/authorized device is supported at a time; if more than
  one is attached, the app refuses to guess and asks you to disconnect one.
- WhatsApp special-casing is limited to `.crypt14`/`.crypt15` database
  filenames; other messaging apps that store content exclusively under
  `Android/data` are not accessible by this or any adb-based tool.
- Incremental (changed-files-only) backup is not implemented yet; every run
  currently backs up the full frozen selection. The manifest/selection
  architecture is intentionally structured (frozen selections keyed by
  device+timestamp, content-addressed by SHA-256) so this can be added later
  without touching the safety model.

## Troubleshooting

- **"no authorized adb device found"**: check USB debugging is enabled, USB
  mode is File Transfer, and you've accepted the on-device authorization
  prompt (`adb devices -l` should show `device`, not blank or
  `unauthorized`).
- **adb not installed**: `sudo apt install android-tools-adb` (Debian/
  Ubuntu) or download Google's `platform-tools` and put it on your `PATH`.
- **Deletion preview shows everything skipped**: usually means the phone
  content changed since the backup, or the backup directory's `_audit/`
  folder was moved/edited — the preview is deliberately conservative.
