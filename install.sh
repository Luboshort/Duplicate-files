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
#    DMG_FILE=/path.dmg  use an already downloaded disk image instead of downloading
# =====================================================================================
set -euo pipefail

REPO="Luboshort/Duplicate-files"
APP_NAME="DuplicateFiles"
BUNDLE_ID="io.github.luboshort.duplicate-files"
DMG_URL="https://github.com/$REPO/releases/latest/download/$APP_NAME.dmg"

TMP="$(mktemp -d /tmp/duplicate-files-install.XXXXXX)"
MNT="$TMP/mnt"
DEST=""
INSTALLED=0
cleanup() {
  local rc=$?
  hdiutil detach -quiet "$MNT" 2>/dev/null || hdiutil detach -quiet -force "$MNT" 2>/dev/null || true
  rm -rf "$TMP"
  # update started from the app failed → start the old version again, so the user is not left without it
  if [ "$rc" -ne 0 ] && [ "$INSTALLED" = 0 ] && [ -n "${WAIT_PID:-}" ] && [ -n "$DEST" ] && [ -d "$DEST" ]; then
    echo "❌ Update failed – starting the previous version again."
    open "$DEST" || true
  fi
}
trap cleanup EXIT

if [ "$(uname -s)" != "Darwin" ]; then echo "❌ Duplicate Files runs on macOS only."; exit 1; fi
if [ "$(uname -m)" != "arm64" ]; then echo "⚠ This build is for Macs with Apple silicon (M1 and newer)."; fi

# started from the app: first wait until it has quit (so a possible restart of the old version is clean)
if [ -n "${WAIT_PID:-}" ]; then
  for _ in $(seq 1 60); do kill -0 "$WAIT_PID" 2>/dev/null || break; sleep 1; done
fi

# destination: given folder, else /Applications if writable, else ~/Applications (no admin rights needed)
if [ -n "${INSTALL_DIR:-}" ]; then
  DEST_DIR="$INSTALL_DIR"
elif [ -w /Applications ]; then
  DEST_DIR="/Applications"
else
  DEST_DIR="$HOME/Applications"
fi
DEST="$DEST_DIR/$APP_NAME.app"

if [ -n "${DMG_FILE:-}" ] && [ -f "$DMG_FILE" ]; then
  cp "$DMG_FILE" "$TMP/$APP_NAME.dmg"
else
  echo "▶ Downloading the latest Duplicate Files…"
  curl -fL --progress-bar -o "$TMP/$APP_NAME.dmg" "$DMG_URL"
fi

echo "▶ Checking the disk image…"
mkdir -p "$MNT"
hdiutil attach -quiet -nobrowse -readonly -noautoopen -mountpoint "$MNT" "$TMP/$APP_NAME.dmg"
SRC_APP="$MNT/$APP_NAME.app"
if [ ! -d "$SRC_APP/Contents/MacOS" ]; then echo "❌ $APP_NAME.app not found in the download."; exit 1; fi

mkdir -p "$DEST_DIR"

# the running app must quit first
osascript -e "tell application id \"$BUNDLE_ID\" to quit" >/dev/null 2>&1 || true
for _ in $(seq 1 20); do pgrep -f "$APP_NAME.app/Contents/MacOS/" >/dev/null || break; sleep 0.5; done

echo "▶ Installing to ${DEST_DIR}…"
NEW="$DEST_DIR/.$APP_NAME.app.new"
rm -rf "$NEW"
ditto "$SRC_APP" "$NEW"
xattr -cr "$NEW" 2>/dev/null || true          # no quarantine flag
# swap: the old version is kept aside until the new one is in place
OLD="$DEST_DIR/.$APP_NAME.app.old"
rm -rf "$OLD"
[ -d "$DEST" ] && mv "$DEST" "$OLD"
if ! mv "$NEW" "$DEST"; then
  [ -d "$OLD" ] && mv "$OLD" "$DEST"
  echo "❌ Could not install to $DEST_DIR"; exit 1
fi
rm -rf "$OLD"
INSTALLED=1
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DEST" 2>/dev/null || true

VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$DEST/Contents/Info.plist" 2>/dev/null || echo '?')"
echo "✅ Duplicate Files $VERSION installed: $DEST"
open "$DEST"
