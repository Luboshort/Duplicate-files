#!/bin/bash
# =====================================================================================
#  Publish to GitHub: build the app, push the source and create a release
#  with the DMG and the zipped .app (the app checks this release for updates).
#
#  Usage:   bash publish.sh
#  Needs:   git (xcode-select --install) and GitHub CLI (brew install gh), logged in once
# =====================================================================================
set -e
trap 'echo "❌ Publishing failed (line $LINENO): $BASH_COMMAND"' ERR

REPO="Luboshort/Duplicate-files"
NAME="DuplicateFiles"
cd "$(dirname "$0")"
VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' app.py)"
TAG="v$VERSION"

command -v git >/dev/null || { echo "❌ git is missing – run: xcode-select --install"; exit 1; }
command -v gh  >/dev/null || { echo "❌ GitHub CLI is missing – install Homebrew (https://brew.sh), then: brew install gh"; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git >/dev/null
gh repo view "$REPO" >/dev/null 2>&1 || gh repo create "$REPO" --public \
    --description "Safe duplicate file finder for macOS – APFS clones, whole duplicate folders, folder compare"

echo "▶ Building $NAME ${VERSION}…"
NO_REVEAL=1 bash build.sh
# stálý název DuplicateFiles.dmg → install.sh stahuje vždy .../releases/latest/download/DuplicateFiles.dmg
OUT="$(mktemp -d /tmp/duplicate-files-release.XXXXXX)"
DMG="$OUT/$NAME.dmg"
ZIP="$OUT/$NAME-$VERSION-app.zip"
cp "$HOME/Desktop/$NAME-$VERSION.dmg" "$DMG"
ditto -c -k --sequesterRsrc --keepParent "$HOME/Applications/$NAME.app" "$ZIP"

echo "▶ Pushing the source code…"
if [ ! -d .git ]; then
  git init -q -b main
  git remote add origin "https://github.com/$REPO.git"
fi
git add -A
git -c user.name="${GIT_NAME:-$(id -F 2>/dev/null || whoami)}" -c user.email="${GIT_EMAIL:-$(whoami)@users.noreply.github.com}" \
    commit -q -m "Duplicate Files $VERSION" || echo "   (nothing new to commit)"
# the repository may already contain e.g. a README created on github.com – merge it, local files win
if git ls-remote --exit-code --heads origin main >/dev/null 2>&1; then
  git fetch -q origin main
  git -c user.name="${GIT_NAME:-$(whoami)}" -c user.email="${GIT_EMAIL:-$(whoami)@users.noreply.github.com}" \
      merge -q --allow-unrelated-histories -X ours -m "Merge GitHub" origin/main || true
fi
git push -u origin main

echo "▶ Creating release ${TAG}…"
# poznámky k vydání: sekce této verze z CHANGELOG.md
CHANGES="$(awk -v v="## $VERSION" 'index($0,v)==1{f=1;next} /^## /{f=0} f' CHANGELOG.md 2>/dev/null || true)"
NOTES="${CHANGES}

**Install or update** – open Terminal and run:

\`\`\`
curl -fsSL https://raw.githubusercontent.com/$REPO/main/install.sh | bash
\`\`\`

For Macs with Apple silicon (M1 and newer)."
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  gh release upload "$TAG" "$DMG" "$ZIP" --repo "$REPO" --clobber
else
  gh release create "$TAG" "$DMG" "$ZIP" --repo "$REPO" --title "Duplicate Files $VERSION" --notes "$NOTES"
fi

rm -rf "$OUT"
echo; echo "✅ Published: https://github.com/$REPO/releases/tag/$TAG"
