# Changelog

## 2.3
- Cloud folders are recognised also in "mirror" mode (Google Drive "My Drive", Dropbox, OneDrive, Box, Creative Cloud Files…), not only in ~/Library/CloudStorage.
- A warning is shown right when a cloud-synced folder is selected; the folder is marked with ☁ and the provider name.

## 2.2
- Sortable columns with a direction arrow (click again to reverse), in both tabs.
- Cloud-synced folders (OneDrive, Google Drive, Dropbox, iCloud Drive): files are never replaced by clones or links there; files that are only in the cloud are not downloaded for verification; a warning is shown before deleting or moving cloud files.

## 2.1
- English / Czech interface (🌐 EN / CZ switch, English by default).
- Checks GitHub for a new version at startup and once a day; "Install and restart" updates the app in place.
- One-line installation from Terminal (no macOS quarantine warning).

## 2.0
- Content fingerprint cache – repeated searches only read new or changed files.
- ⚡ Free up space – replaces all verified duplicates on APFS with clones in one step.
- Excluded folders.
- Whole duplicate folders view, with a safe "move whole folder to Trash".

## 1.x
- Duplicate search, compare two places with "Fill in", permission fixer, APFS clone replacement and byte-exact safety checks before every action.
