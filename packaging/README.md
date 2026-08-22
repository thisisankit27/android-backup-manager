# Packaging

Builds the desktop app into a Windows installer and an Ubuntu `.deb`.

PyInstaller **cannot cross-compile**: Windows must be built on Windows and
Linux on Linux. CI does both in `.github/workflows/release.yml`; the steps
below are for building locally.

## Layout

```
packaging/
  build.py            builds frontend + PyInstaller bundle (both platforms)
  app.spec            PyInstaller spec
  linux/
    build_deb.sh      .deb from the bundle
    51-android.rules  udev rules so adb works without sudo
    android-backup-manager.desktop
  windows/
    installer.iss     Inno Setup script
```

Output goes to `dist/` (bundle) and `packaging/installer-output/`
(installers). Both are gitignored.

## Ubuntu

```bash
sudo apt install -y libgirepository1.0-dev libcairo2-dev pkg-config \
  gir1.2-webkit2-4.1 libwebkit2gtk-4.1-dev python3-dev build-essential

pip install -r backend/requirements.txt \
            -r backend/requirements-desktop.txt pygobject

python packaging/build.py
packaging/linux/build_deb.sh 0.1.0
```

Install and run:

```bash
sudo apt install ./packaging/installer-output/android-backup-manager_0.1.0_amd64.deb
android-backup-manager
```

### Why `.deb` and not AppImage

`adb` cannot talk to a phone as a normal user without udev rules in
`/etc/udev/rules.d`. Only a package with an install step can put them there.
An AppImage would leave every user adding them by hand.

### Dependencies, and one trap

PyInstaller bundles GTK and the `gi` bindings, but **not WebKit** — the
WebKit2 typelib and library are resolved from the system at runtime, so
`libwebkit2gtk-4.1-0` and `gir1.2-webkit2-4.1` are hard dependencies.

GTK is deliberately **not** listed. `libwebkit2gtk-4.1-0` already depends on
it, and naming it directly breaks installation: Ubuntu's 64-bit `time_t`
transition renamed the package to `libgtk-3-0t64` on 24.04+, so a literal
`libgtk-3-0` is unsatisfiable there.

## Windows

Needs Python 3.12+, Node 20+ and [Inno Setup 6](https://jrsoftware.org/isdl.php).

```powershell
pip install -r backend\requirements.txt -r backend\requirements-desktop.txt
python packaging\build.py
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DAppVersion=0.1.0 packaging\windows\installer.iss
```

### SmartScreen

The installer is **unsigned**, so Windows shows *"Windows protected your
PC"*. Users must click **More info → Run anyway**.

Fixing this needs an OV or EV code-signing certificate (roughly
$200–400/year) — a purchasing decision, not a build one. Until then the
download page has to tell people what they will see, or most will assume
the app is malware.

### USB drivers

`adb` needs the manufacturer's USB driver on Windows; Google's driver only
covers Pixel/Nexus. Expect *"my phone doesn't show up"* to be the most
common support request.

## Bundle size

The first Linux build was 304 MB. PyInstaller's `gi` hook collects every
installed GTK icon theme — Yaru, Adwaita, HighContrast — plus theme engines,
about 170 MB of it. The app renders its entire interface inside a WebView and
the compositor draws the window frame, so none of it can ever be displayed.
`app.spec` drops those (~28,000 files) and `uvloop`, which a single-user
loopback server has no use for.

Result: ~108 MB bundle, ~43 MB compressed `.deb`.

## Releasing

Tag and push:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

Both runners build, and the artifacts are attached to a GitHub Release. To
test the pipeline without tagging, run the workflow manually
(**Actions → Release → Run workflow**) — it builds and uploads artifacts but
publishes no Release.

## Troubleshooting

**WebKit dies with `undefined symbol: __libc_pthread_init`** — you launched
from a terminal inside a snap (the VS Code snap does this). Snap injects
`/snap/core20` libraries that are incompatible with system WebKit. Launch
from a normal terminal or the desktop entry.

**`Failed to load module "canberra-gtk-module"`** — harmless. It is a sound
event module the app does not use.
