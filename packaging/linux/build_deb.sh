#!/usr/bin/env bash
#
# Build the .deb from the PyInstaller output in dist/android-backup-manager.
#
#   packaging/linux/build_deb.sh 1.2.3
#
# A .deb rather than an AppImage specifically because of udev: adb cannot
# talk to a phone as a normal user without rules in /etc/udev/rules.d, and
# only a package with an install step can put them there. An AppImage would
# leave every user doing it by hand.
set -euo pipefail

VERSION="${1:?usage: build_deb.sh <version>}"
ARCH="$(dpkg --print-architecture)"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BUNDLE="$ROOT/dist/android-backup-manager"
OUT="$ROOT/packaging/installer-output"

if [[ ! -x "$BUNDLE/android-backup-manager" ]]; then
  echo "error: $BUNDLE/android-backup-manager not found." >&2
  echo "Run packaging/build.py first." >&2
  exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

PKGDIR="$STAGE/android-backup-manager_${VERSION}_${ARCH}"

install -d "$PKGDIR/DEBIAN"
install -d "$PKGDIR/opt/android-backup-manager"
install -d "$PKGDIR/usr/share/applications"
install -d "$PKGDIR/usr/share/icons/hicolor/256x256/apps"
install -d "$PKGDIR/lib/udev/rules.d"
install -d "$PKGDIR/usr/bin"

cp -a "$BUNDLE/." "$PKGDIR/opt/android-backup-manager/"
install -m 644 "$HERE/android-backup-manager.desktop" "$PKGDIR/usr/share/applications/"
install -m 644 "$HERE/51-android.rules" "$PKGDIR/lib/udev/rules.d/51-android.rules"

if [[ -f "$HERE/icon.png" ]]; then
  install -m 644 "$HERE/icon.png" \
    "$PKGDIR/usr/share/icons/hicolor/256x256/apps/android-backup-manager.png"
fi

ln -s /opt/android-backup-manager/android-backup-manager \
  "$PKGDIR/usr/bin/android-backup-manager"

INSTALLED_KB="$(du -sk "$PKGDIR" | cut -f1)"

# WebKit is NOT bundled -- PyInstaller carries GTK and the gi bindings, but
# the WebKit2 typelib and library are resolved from the system at runtime,
# so both are hard dependencies.
#
# GTK is deliberately NOT listed. libwebkit2gtk-4.1-0 already depends on it,
# and naming it directly would break installation: Ubuntu's 64-bit time_t
# transition renamed the package to libgtk-3-0t64 on 24.04+, so a literal
# "libgtk-3-0" is unsatisfiable there.
#
# adb is Recommends rather than Depends: the app can fetch platform-tools
# itself, and apt installs Recommends by default anyway.
cat > "$PKGDIR/DEBIAN/control" <<EOF
Package: android-backup-manager
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: libwebkit2gtk-4.1-0, gir1.2-webkit2-4.1
Recommends: adb | android-tools-adb
Installed-Size: $INSTALLED_KB
Maintainer: Ankit Srivastava <ankitsrivastava260517@gmail.com>
Homepage: https://github.com/thisisankit27/android-backup-manager
Description: Back up an Android phone and verify every copy
 Copies personal files off an Android phone over adb, verifies every copy
 with SHA-256, and -- as a separate, explicitly confirmed step -- deletes
 only the exact files that were verified.
 .
 Runs entirely on this machine. Nothing is uploaded anywhere.
EOF

cat > "$PKGDIR/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e

# Pick up the adb udev rules without requiring a reboot. A phone that is
# already plugged in needs replugging either way.
if [ -x /sbin/udevadm ] || [ -x /bin/udevadm ] || command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules >/dev/null 2>&1 || true
    udevadm trigger --subsystem-match=usb >/dev/null 2>&1 || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi

if ! command -v adb >/dev/null 2>&1; then
    echo "Note: adb was not found. Install it with:"
    echo "    sudo apt install android-tools-adb"
    echo "or let the app download the official platform-tools on first run."
fi

exit 0
EOF
chmod 755 "$PKGDIR/DEBIAN/postinst"

cat > "$PKGDIR/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules >/dev/null 2>&1 || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
fi
exit 0
EOF
chmod 755 "$PKGDIR/DEBIAN/postrm"

mkdir -p "$OUT"
DEB="$OUT/android-backup-manager_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$PKGDIR" "$DEB"

echo
echo "Built: $DEB"
du -h "$DEB" | cut -f1 | sed 's/^/Size:  /'
