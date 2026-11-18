#!/bin/bash
# =====================================================================================
#  Duplicate Files – install / update from the latest GitHub release
#
#    curl -fsSL https://raw.githubusercontent.com/Luboshort/Duplicate-files/main/install.sh | bash
#
#  Installs to /Applications (or ~/Applications without admin rights) and starts the app.
#  A file downloaded by curl does not get the macOS "downloaded from the internet"
#  (quarantine) flag, so the app without a paid Apple signature is not blocked.
#
#  Optional environment variables (used by the app's own updater):
#    INSTALL_DIR=/path   install into this folder
#    WAIT_PID=1234       wait until this process (the running app) has quit
# =====================================================================================
set -euo pipefail

REPO="Luboshort/Duplicate-files"
APP_NAME="DuplicateFiles"
BUNDLE_ID="io.github.luboshort.duplicate-files"
DMG_URL="https://github.com/$REPO/releases/latest/download/$APP_NAME.dmg"

TMP="$(mktemp -d /tmp/duplicate-files-install.XXXXXX)"
MNT="$TMP/mnt"
cleanup() {
  hdiutil detach -quiet "$MNT" 2>/dev/null || hdiutil detach -quiet -force "$MNT" 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT

if [ "$(uname -s)" != "Darwin" ]; then echo "❌ Duplicate Files runs on macOS only."; exit 1; fi
if [ "$(uname -m)" != "arm64" ]; then echo "⚠ This build is for Macs with Apple silicon (M1 and newer)."; fi

echo "▶ Downloading the latest Duplicate Files…"
curl -fL --progress-bar -o "$TMP/$APP_NAME.dmg" "$DMG_URL"

echo "▶ Checking the disk image…"
mkdir -p "$MNT"
hdiutil attach -quiet -nobrowse -readonly -noautoopen -mountpoint "$MNT" "$TMP/$APP_NAME.dmg"
SRC_APP="$MNT/$APP_NAME.app"
if [ ! -d "$SRC_APP/Contents/MacOS" ]; then echo "❌ $APP_NAME.app not found in the download."; exit 1; fi

# destination: given folder, else /Applications if writable, else ~/Applications (no admin rights needed)
if [ -n "${INSTALL_DIR:-}" ]; then
  DEST_DIR="$INSTALL_DIR"
elif [ -w /Applications ]; then
  DEST_DIR="/Applications"
else
  DEST_DIR="$HOME/Applications"
fi
mkdir -p "$DEST_DIR"
DEST="$DEST_DIR/$APP_NAME.app"

# the running app must quit first
if [ -n "${WAIT_PID:-}" ]; then
  for _ in $(seq 1 60); do kill -0 "$WAIT_PID" 2>/dev/null || break; sleep 1; done
fi
osascript -e "tell application id \"$BUNDLE_ID\" to quit" >/dev/null 2>&1 || true
for _ in $(seq 1 20); do pgrep -f "$APP_NAME.app/Contents/MacOS/" >/dev/null || break; sleep 0.5; done

echo "▶ Installing to $DEST_DIR…"
NEW="$DEST_DIR/.$APP_NAME.app.new"
rm -rf "$NEW"
ditto "$SRC_APP" "$NEW"
xattr -cr "$NEW" 2>/dev/null || true          # no quarantine flag
rm -rf "$DEST"
mv "$NEW" "$DEST"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DEST" 2>/dev/null || true

VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$DEST/Contents/Info.plist" 2>/dev/null || echo '?')"
echo "✅ Duplicate Files $VERSION installed: $DEST"
open "$DEST"
