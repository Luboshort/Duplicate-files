#!/bin/bash
# =====================================================================================
#  Build the standalone macOS app (Python + Tkinter) and an installer DMG
#  Tested on: macOS 26 Tahoe, Apple Silicon (M4), Python from python.org, PyInstaller 6
#
#  Usage:   bash build.sh            (run from anywhere; the script finds its own folder)
#  Result:  ~/Applications/DuplicateFiles.app  +  ~/Desktop/DuplicateFiles-<version>.dmg
# =====================================================================================
set -e
trap 'echo "❌ Build failed (line $LINENO): $BASH_COMMAND"' ERR

# ----------------------------- PROJECT SETTINGS --------------------------------------
NAME="DuplicateFiles"                       # .app and DMG name – no spaces or diacritics
MAIN_FILE="app.py"                          # must contain a line: APP_VERSION = "x.y"
BUNDLE_ID="io.github.luboshort.duplicate-files"

# Extra data bundled into the app: "source:target_inside_app" (relative to the project)
BUNDLE_DATA=(
  "tkinterdnd2/tkdnd:tkinterdnd2/tkdnd"     # native drag & drop library
)
# Modules PyInstaller may not find on its own (imported inside try/except)
HIDDEN_IMPORTS=(
  "tkinterdnd2"
  "preklady"
)
# Folders and disks can be dropped onto the app icon
DOC_TYPES='[{"CFBundleTypeName":"Folder","CFBundleTypeRole":"Viewer","LSItemContentTypes":["public.folder","public.volume"]}]'
APPLE_EVENTS_TEXT="Duplicate Files controls Finder to create aliases and move files to the Trash."
# --------------------------------------------------------------------------------------

SRC="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' "$SRC/$MAIN_FILE")"
VERSION="${VERSION:-1.0}"

# 1) Python: on Apple Silicon a NATIVE arm64 build (not Rosetta) with Tcl/Tk 8.6 or newer
pick_python() {
  PY=""; PYRUN=""; PYARCH=""; PYTCL=""
  local K=(/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
           /Library/Frameworks/Python.framework/Versions/*/bin/python3
           /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3)
  local T='import tkinter, platform; print(platform.machine(), tkinter.TclVersion)' C I
  # Tk older than 8.6 (Apple's system Python /usr/bin/python3) leaves the window blank on new macOS
  tk_ok() { case "$1" in 8.6*|9.*|1[0-9].*) return 0 ;; *) return 1 ;; esac; }
  if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then
    for C in "${K[@]}"; do
      [ -x "$C" ] || continue
      I="$(arch -arm64 "$C" -c "$T" 2>/dev/null)" || continue
      tk_ok "${I#* }" || { echo "   (skipping $C – outdated Tcl/Tk ${I#* })"; continue; }
      case "$I" in arm64*) PY="$C"; PYRUN="arch -arm64 $C"; PYARCH=arm64; PYTCL="${I#* }"; return 0 ;; esac
    done
    return 1
  fi
  for C in "${K[@]}"; do
    [ -x "$C" ] || continue
    I="$("$C" -c "$T" 2>/dev/null)" || continue
    tk_ok "${I#* }" || { echo "   (skipping $C – outdated Tcl/Tk ${I#* })"; continue; }
    [ -z "$PY" ] && { PY="$C"; PYRUN="$C"; PYARCH="${I%% *}"; PYTCL="${I#* }"; }
    case "${I#* }" in 8.*) PY="$C"; PYRUN="$C"; PYARCH="${I%% *}"; PYTCL="${I#* }"; break ;; esac
  done
  [ -n "$PY" ]
}
if ! pick_python; then
  echo "❌ No suitable Python with Tkinter (Tcl/Tk 8.6 or newer) found."
  echo "   Apple's system Python (/usr/bin/python3) has an outdated Tk 8.5 – the app window would stay blank."
  echo "   Install Python from https://www.python.org/downloads/macos/ (.pkg installer) and run this again."
  exit 1
fi
RUN=""; [ "$PYARCH" = "arm64" ] && RUN="arch -arm64"
echo "▶ Building $NAME $VERSION with $PY ($PYARCH, Tcl/Tk $PYTCL)"

# 2) Temporary work folder with its own venv and PyInstaller (the system stays clean)
WORK="$(mktemp -d /tmp/app-build.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
rsync -a --exclude '.git' --exclude '__pycache__' --exclude '*.dmg' --exclude '*.zip' "$SRC/" "$WORK/src/"
xattr -cr "$WORK/src" 2>/dev/null || true          # quarantine from a downloaded zip would block libraries
$PYRUN -m venv "$WORK/venv"
$RUN "$WORK/venv/bin/python" -m pip install --quiet --upgrade pip pyinstaller
[ -f "$SRC/requirements.txt" ] && $RUN "$WORK/venv/bin/python" -m pip install --quiet -r "$SRC/requirements.txt"

# 3) Build
ARGS=(--noconfirm --clean --log-level WARN --windowed --name "$NAME"
      --osx-bundle-identifier "$BUNDLE_ID" --paths "$WORK/src")
for P in "${BUNDLE_DATA[@]}";    do ARGS+=(--add-data "$WORK/src/${P%%:*}:${P#*:}"); done
for M in "${HIDDEN_IMPORTS[@]}"; do ARGS+=(--hidden-import "$M"); done
echo "▶ PyInstaller (1–2 minutes)…"
cd "$WORK/src"
$RUN "$WORK/venv/bin/python" -m PyInstaller "${ARGS[@]}" --distpath "$WORK/dist" --workpath "$WORK/build" "$MAIN_FILE"
APP="$WORK/dist/$NAME.app"
PL="$APP/Contents/Info.plist"

# 4) Info.plist: version, Retina, document types, display name
plutil -replace CFBundleShortVersionString -string "$VERSION" "$PL"
plutil -replace CFBundleVersion -string "$VERSION" "$PL"
plutil -replace CFBundleDisplayName -string "Duplicate Files" "$PL"
plutil -replace NSHighResolutionCapable -bool YES "$PL"
[ -n "$DOC_TYPES" ] && plutil -replace CFBundleDocumentTypes -json "$DOC_TYPES" "$PL"
[ -n "$APPLE_EVENTS_TEXT" ] && plutil -replace NSAppleEventsUsageDescription -string "$APPLE_EVENTS_TEXT" "$PL"

# 5) Ad-hoc signature: file by file from the inside out, NOT --deep (codesign --deep crashed with Bus error)
echo "▶ Signing…"
xattr -cr "$APP" 2>/dev/null || true
# note: the loop must not end with a non-zero status (the last file may not be Mach-O) – set -e would stop silently
find "$APP/Contents" -type f -print0 | while IFS= read -r -d '' F; do
  if file -b "$F" | grep -q "Mach-O"; then
    codesign --force --sign - "$F" >/dev/null 2>&1 || echo "   (cannot sign: ${F#$APP/})"
  fi
done
find "$APP/Contents" -type d -name "*.framework" -depth -print0 | while IFS= read -r -d '' F; do
  codesign --force --sign - "$F" >/dev/null 2>&1 || true
done
codesign --force --sign - "$APP"
codesign --verify "$APP" && echo "   signature OK"

# 6) Install to ~/Applications
mkdir -p "$HOME/Applications"
rm -rf "$HOME/Applications/$NAME.app"
ditto "$APP" "$HOME/Applications/$NAME.app"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$HOME/Applications/$NAME.app" 2>/dev/null || true

# 7) DMG for other Macs – one file, transfers (OneDrive, Teams, e-mail…) cannot damage the app
echo "▶ Creating DMG…"
D="$WORK/dmg"; mkdir -p "$D"
ditto "$APP" "$D/$NAME.app"
ln -s /Applications "$D/Applications"
cat > "$D/How to install.txt" <<TXT
Duplicate Files $VERSION

Recommended: install from Terminal instead (no macOS warning):
   curl -fsSL https://raw.githubusercontent.com/Luboshort/Duplicate-files/main/install.sh | bash

Manually: drag "$NAME" onto "Applications". If macOS says it cannot verify the app:
"Done" → System Settings → Privacy & Security → "Open Anyway" (once).

For Macs with Apple silicon (M1 and newer).

---
CZ: Doporučeno nainstalovat z Terminálu (bez varování macOS) – příkaz výše.
Ručně: přetáhni „${NAME}“ do „Applications“; když macOS aplikaci zablokuje:
„Hotovo“ → Nastavení systému → Soukromí a zabezpečení → „Přesto otevřít“.
TXT
DMG="$HOME/Desktop/$NAME-$VERSION.dmg"
rm -f "$DMG"
hdiutil create -quiet -volname "Duplicate Files $VERSION" -srcfolder "$D" -fs HFS+ -format UDZO -ov "$DMG"
hdiutil verify -quiet "$DMG" && echo "   DMG OK"

echo; echo "✅ Done."
echo "   App:            $HOME/Applications/$NAME.app"
echo "   For other Macs: $DMG"
[ -z "$NO_REVEAL" ] && open -R "$HOME/Applications/$NAME.app" || true
