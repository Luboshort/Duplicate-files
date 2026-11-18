# Duplicate Files

A safe duplicate file finder for macOS (Apple silicon, M1 and newer). Drop a disk or folder into the window and it finds duplicate files and whole duplicate folders. You can then free up space without losing a single file.

The interface is in **English** and **Czech** (🌐 EN / CZ switch at the top right).

## Download

Get the latest **DuplicateFiles-x.y.dmg** from [Releases](https://github.com/Luboshort/Duplicate-files/releases/latest), open it and drag the app to *Applications*.

The app is not notarized. The first time you open it, macOS says it cannot verify it: click *Done*, then open *System Settings → Privacy & Security* and click *Open Anyway*. You only need to do this once.

The app checks GitHub for a new version at startup and offers to download it. You can turn this off in the ⚙ menu.

## Features

- **Find duplicates** by name, size, modification date and creation date, with an optional byte-exact **content verification**.
  - Content fingerprints are cached, so repeated searches of a large backup disk only read new or changed files.
- **Whole duplicate folders** (View → Whole folders). Identical copies of a folder tree are shown as a single item.
- **⚡ Free up space**: one click replaces all verified duplicates on an APFS disk with **APFS clones**.
  - Every file stays in place with its name, tags and dates; the data is stored only once.
- **Other actions**:
  - Move to Trash, or move to a folder (keeps the subfolder structure).
  - Replace with a hard link, Finder alias or symbolic link.
  - Export the list to CSV.
- **Compare two places**: see what is only in A, only in B, or different. *Fill in* copies the missing files so both places end up with the same content. It never deletes or overwrites anything.
- **Unlock and fix permissions** in a folder or disk, with a preview and a saved undo record.
- **Excluded folders** (⚙ → Excluded folders): a specific path, or a folder name anywhere such as `node_modules`.

## Safety principles

- **Nothing is removed without proof.** Right before any file is moved to the Trash, moved elsewhere or replaced, it is compared **byte by byte** with a kept original that can be read completely.
  - If the original is damaged, unreadable, changed since the search or missing, the file is left untouched.
- **Whole folders are checked again before the Trash.** Each folder is rescanned (including hidden and system files) and compared file by file. Any extra, missing or different file means the folder stays.
- **Files that must stay are protected.** Files inside packages and libraries (Photos libraries, `.app`, `.git`) are never deleted. Network disks are never sent to the "Trash", because they have no Trash and files there would be deleted immediately.
- **Every action is logged** in `~/Library/Logs/DuplicitniSoubory/`.

## Build from source

Requires Python from [python.org](https://www.python.org/downloads/macos/). Apple's system Python has an outdated Tk, and the window would stay blank.

```bash
git clone https://github.com/Luboshort/Duplicate-files.git
cd Duplicate-files
bash build.sh        # → ~/Applications/DuplicateFiles.app and ~/Desktop/DuplicateFiles-x.y.dmg
```

To publish a new release (maintainer), raise `APP_VERSION` in `app.py`, then run `bash publish.sh`. This needs `git` and the GitHub CLI `gh`.

## Data locations

| What | Where |
|---|---|
| Settings, fingerprint cache, permission undo records | `~/Library/Application Support/DuplicitniSoubory/` |
| Action log and error log | `~/Library/Logs/DuplicitniSoubory/` |

## Credits

Drag & drop uses [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2) (tkdnd).
