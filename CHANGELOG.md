# Changelog

## 2.7
- New tab **Content compare**: lists files (not folders) from place A that are nowhere in place B, regardless of folder structure. A match means the same name, size, creation and modification date and time (2 s tolerance).
  - Same size and times under another name: the name is red, and the matching files in B are listed below it in green.
  - Same name but a different size or time: the files in B are listed below it, with the differences in red.
  - Double-click, Return or the context menu shows any listed file in Finder (also Quick Look and Copy path). Sortable columns, filter, CSV export, ⇄ swaps the direction without rescanning.
  - One place may be inside the other (e.g. "is everything in this folder somewhere else on the disk?") – the nested folder is then left out of the larger one.
- The "Duplicates" tab name is now translated in English.

## 2.6
- Cloud-synced subfolders inside a scanned folder are detected while scanning (Google Drive mirror, Dropbox, OneDrive, iCloud, File Provider folders – also by their hidden marker files and extended attributes).
- Files in cloud-synced folders are protected: shown with ☁, never marked, deleted, moved or replaced; they can only be the kept original. A warning lists the cloud folders after each search.

## 2.5
- New look matching Katalog souborů: light pane inside the tabs with a thin rounded outline, framed lists with both scrollbars, a status bar at the bottom (status, language, version, Check for updates).
- A new version is offered in a yellow bar at the top (Install and restart · What's new · Hide); after an update a green bar confirms the new version.

## 2.4
- One-click update: the app asks once – Yes downloads the new version while the app is still running, then it closes, updates itself and restarts. If the download fails, the app keeps running unchanged; if the installation fails, the previous version starts again.

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
