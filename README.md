# Duplicate Files

🇨🇿 [Návod česky](NAVOD_CZ.md)

A safe duplicate file finder for macOS (Apple silicon, M1 and newer). Drop a disk or folder into the window and it finds duplicate files and whole duplicate folders. You can then free up space without losing a single file.

The interface is in **English** and **Czech** (🌐 EN / CZ switch at the top right).

## Installation

Open Terminal and paste this command:

```
curl -fsSL https://raw.githubusercontent.com/Luboshort/Duplicate-files/main/install.sh | bash
```

It downloads the latest version, installs it to *Applications* (or to `~/Applications` without admin rights) and starts it.

**Why not download the DMG in a browser?** A file downloaded by a browser gets the macOS "downloaded from the internet" flag. An app without a paid Apple signature is then blocked with a possible-malware warning, and on company Macs it often cannot be allowed at all. A file downloaded from Terminal does not get this flag.

**Updates:** the app checks GitHub at startup and then once a day. When a new version exists, it asks once: **Yes** downloads it, the app updates itself and restarts – nothing else to do. You can also run the command above again at any time. Use ⚙ → *Check for updates…* to check manually, or turn the automatic check off there.

**Uninstall:** move `DuplicateFiles.app` from *Applications* to the Trash. Settings are in `~/Library/Application Support/DuplicitniSoubory/`.

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
- **Content compare**: lists files from place A that are nowhere in place B, whatever folder they are in (match by name, size, and creation and modification date and time). A file found in B under another name is shown in red with the matching files below it in green; a file with the same name but a different size or time is shown with the differences in red. Optionally, files with the same name and size but different dates are compared by content, and identical ones are left out. Any file can be shown in Finder. Read-only.
- **Unlock and fix permissions** in a folder or disk, with a preview and a saved undo record.
- **Cloud-synced folders** (OneDrive, Google Drive, Dropbox, iCloud Drive) – also when they are subfolders of the scanned folder: their files are shown with ☁ but never marked, deleted, moved or replaced; only copies outside the cloud can be removed. Files that are only in the cloud are never downloaded just to compare them.
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

To publish a new release (maintainer):
1. Raise `APP_VERSION` in `app.py`.
2. Add a section to `CHANGELOG.md`.
3. Run `bash publish.sh`. This needs `git` and the GitHub CLI `gh`.

## Data locations

| What | Where |
|---|---|
| Settings, fingerprint cache, permission undo records | `~/Library/Application Support/DuplicitniSoubory/` |
| Action log and error log | `~/Library/Logs/DuplicitniSoubory/` |

## Credits

Drag & drop uses [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2) (tkdnd).
