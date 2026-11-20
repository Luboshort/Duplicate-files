#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Duplicitní soubory – macOS aplikace (Python 3 + Tkinter/ttk)

Přetažením disku nebo složky do okna (nebo na ikonu v Docku) se spustí hledání
duplicitních souborů podle zvolených kritérií (název, velikost, datum změny,
datum vytvoření, volitelně ověření obsahu). S nalezenými duplicitami jde dál
pracovat: přesunout do Koše, přesunout jinam, nahradit APFS klonem, pevným
odkazem, aliasem Finderu nebo symbolickým odkazem, exportovat přehled do CSV.
"""

APP_VERSION = "2.5"
APP_TITLE = "Duplicitní soubory"   # přeloží se níže (T ještě není definováno)

import csv
import sqlite3
import ctypes
import struct
import datetime
import filecmp
import hashlib
import json
import os
import queue
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import uuid

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont

try:  # drag & drop z Finderu (přibalená knihovna tkinterdnd2)
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - ukáže se v okně
    TkinterDnD = None
    DND_FILES = None
    DND_IMPORT_ERROR = exc

IS_MAC = sys.platform == "darwin"
SUPPORT_DIR = os.path.expanduser("~/Library/Application Support/DuplicitniSoubory")
LOG_DIR = os.path.expanduser("~/Library/Logs/DuplicitniSoubory")
SETTINGS_FILE = os.path.join(SUPPORT_DIR, "nastaveni.json")


# ---------------- jazyk (výchozí angličtina) ----------------
def _initial_lang():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            lang = json.load(fh).get("lang", "en")
    except (OSError, ValueError, AttributeError):
        lang = "en"
    return lang if lang in ("en", "cs") else "en"


LANG = os.environ.get("DUPLICATE_FILES_LANG") or _initial_lang()
try:
    from preklady import EN as _EN
except ImportError:                      # bez souboru s překlady zůstane čeština
    _EN = {}


def T(text, *args):
    """Přeloží text (zdrojem je čeština). Šablony z f-stringů mají místa {0}, {1:.0f}…"""
    if LANG == "en":
        text = _EN.get(text, text)
    return text.format(*args) if args else text


APP_TITLE = T("Duplicitní soubory")
GITHUB_REPO = "Luboshort/Duplicate-files"
INSTALL_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/install.sh"

MAX_GROUPS_SHOWN = 3000          # do okna nejvýš tolik skupin (~10 000 řádků)
MAX_ROWS_PER_GROUP = 300         # a v jedné skupině nejvýš tolik souborů
CHUNK = 64 * 1024                # pro rychlý (částečný) otisk souboru

# ======================================================================================
#  LOGIKA (bez GUI – testovatelná samostatně)
# ======================================================================================

SKIP_FILE_NAMES = {".DS_Store", ".localized", "Icon\r", ".VolumeIcon.icns"}
SKIP_DIR_NAMES = {".Trashes", ".Trash", ".Spotlight-V100", ".fseventsd", ".DocumentRevisions-V100",
                  ".TemporaryItems", ".MobileBackups", ".PKInstallSandboxManager",
                  "$RECYCLE.BIN", "System Volume Information"}
# při prohledávání celého systémového disku „/“ – jinak by se soubory našly dvakrát (firmlinky)
SYSTEM_ROOT_SKIP = {"/System", "/Volumes", "/dev", "/private/var/vm", "/cores", "/.vol", "/Network"}
# macOS „balíčky“ – ve Finderu vypadají jako jeden soubor, uvnitř jsou tisíce souborů
PACKAGE_EXT = {".app", ".photoslibrary", ".photolibrary", ".musiclibrary", ".tvlibrary", ".imovielibrary",
               ".fcpbundle", ".logicx", ".band", ".lrlibrary", ".lrdata", ".bundle", ".framework",
               ".plugin", ".kext", ".appex", ".xcodeproj", ".xcworkspace", ".xcarchive",
               ".pages", ".numbers", ".key", ".rtfd", ".sparsebundle", ".pkg", ".mpkg",
               ".download", ".dtBase2", ".aplibrary", ".photosLibrary"}
PACKAGE_EXT = {e.lower() for e in PACKAGE_EXT}


class Cancelled(Exception):
    pass


class FileInfo:
    __slots__ = ("path", "name", "size", "mtime", "btime", "dev", "ino", "root", "marked", "locked", "clone",
                 "ctime", "dataless")

    def __init__(self, path, name, size, mtime, btime, dev, ino, root, locked=False, ctime=0.0, dataless=False):
        self.path, self.name, self.size = path, name, size
        self.mtime, self.btime, self.dev, self.ino, self.root = mtime, btime, dev, ino, root
        self.marked = False
        self.locked = locked
        self.clone = None        # identifikátor dat APFS klonu (stejný = data jsou na disku jen jednou)
        self.ctime = ctime       # čas změny metadat – mění se při každém zápisu (kvůli paměti otisků)
        self.dataless = dataless  # jen v cloudu, nestažený (OneDrive/Google Drive/iCloud „jen online“)

    def __repr__(self):
        return f"FileInfo({self.path!r})"


class Group:
    __slots__ = ("files", "verified")

    def __init__(self, files, verified=False):
        self.files = files
        self.verified = verified

    @property
    def total(self):
        return sum(f.size for f in self.files)

    def _classes(self):
        """Soubory rozdělené podle toho, zda sdílejí data (APFS klon)."""
        cls = {}
        for f in self.files:
            cls.setdefault(f.clone if f.clone else (T("vlastní"), id(f)), []).append(f)
        return list(cls.values())

    @property
    def wasted(self):
        """Kolik místa se ještě uvolní – klony, které už sdílejí data, se nepočítají."""
        if not self.files:
            return 0
        sizes = [c[0].size for c in self._classes()]
        return sum(sizes) - max(sizes)

    @property
    def merged(self):
        """Všechny soubory skupiny už sdílejí jedna data (byly nahrazeny klonem)."""
        return len(self.files) > 1 and len(self._classes()) == 1

    @property
    def name(self):
        return self.files[0].name if self.files else ""


SF_DATALESS = 0x40000000                 # macOS: obsah souboru je jen v cloudu (čtení ho stáhne)
CLOUD_MARKERS = ("/Library/CloudStorage/", "/Library/Mobile Documents/")


# skryté soubory, podle kterých jde poznat kořen synchronizované složky (i v režimu „zrcadlit“)
CLOUD_MARKER_FILES = {
    ".tmp.drivedownload": "Google Drive", ".tmp.driveupload": "Google Drive",
    ".shortcut-targets-by-id": "Google Drive", ".dropbox": "Dropbox", ".dropbox.cache": "Dropbox",
    ".849C9593-D756-4E56-8D6E-42412F2A707B": "OneDrive", ".sync": "Sync.com",
}
# typické názvy synchronizovaných složek přímo v domovské složce
CLOUD_HOME_NAMES = {"my drive": "Google Drive", "google drive": "Google Drive", "dropbox": "Dropbox",
                    "onedrive": "OneDrive", "box": "Box", "box sync": "Box",
                    "creative cloud files": "Adobe Creative Cloud", "pcloud drive": "pCloud", "mega": "MEGA",
                    "nextcloud": "Nextcloud", "owncloud": "ownCloud", "icloud drive": "iCloud Drive"}
_CLOUD_CACHE = {}


def _cloud_of_dir(d):
    """Poskytovatel cloudu pro složku `d` (prochází nadřazené složky), nebo ""."""
    if d in _CLOUD_CACHE:
        return _CLOUD_CACHE[d]
    res = ""
    low = d.lower()
    if "/library/cloudstorage/" in low + "/":
        name = d.split("/Library/CloudStorage/", 1)[-1].split("/", 1)[0] if "/Library/CloudStorage/" in d else ""
        res = ("Google Drive" if name.startswith("GoogleDrive") else "OneDrive" if name.startswith("OneDrive")
               else "Dropbox" if name.startswith("Dropbox") else "Box" if name.startswith("Box")
               else name.split("-")[0] or "cloud")
    elif "/library/mobile documents/" in low + "/":
        res = "iCloud Drive"
    else:
        home = os.path.expanduser("~")
        base = os.path.basename(d).lower()
        if os.path.dirname(d) == home and (base in CLOUD_HOME_NAMES or base.startswith("onedrive")):
            res = CLOUD_HOME_NAMES.get(base, "OneDrive")
        else:
            names = [m for m in CLOUD_MARKER_FILES if os.path.lexists(os.path.join(d, m))]
            if names:
                res = CLOUD_MARKER_FILES[names[0]]
            elif fs_type(d).lower().startswith(("dfsfuse", "osxfuse")):
                res = "Google Drive"
        parent = os.path.dirname(d)
        if not res and parent != d and len(parent) > 1:
            res = _cloud_of_dir(parent)
    if len(_CLOUD_CACHE) > 200_000:
        _CLOUD_CACHE.clear()
    _CLOUD_CACHE[d] = res
    return res


def cloud_provider(path):
    """Název cloudu, se kterým se soubor/složka synchronizuje (Google Drive, OneDrive…), nebo ""."""
    return _cloud_of_dir(path if os.path.isdir(path) and not os.path.islink(path) else os.path.dirname(path))


def is_cloud(path):
    """Složka synchronizovaná s cloudem (OneDrive, Google Drive, Dropbox, iCloud Drive…)."""
    return bool(cloud_provider(path))


def is_dataless(path):
    try:
        return bool(getattr(os.lstat(path), "st_flags", 0) & SF_DATALESS)
    except OSError:
        return False


class ScanOptions:
    def __init__(self, hidden=False, packages=False, min_size=1, exclude=()):
        self.hidden, self.packages, self.min_size = hidden, packages, min_size
        self.exclude = tuple(exclude)
        # položka s „/“ = konkrétní složka (cesta), bez „/“ = název složky kdekoli (např. node_modules)
        self.excl_paths = {norm_name(os.path.realpath(os.path.expanduser(x))).rstrip("/")
                           for x in self.exclude if "/" in x}
        self.excl_names = {norm_name(x) for x in self.exclude if x and "/" not in x}

    def signature(self):
        return (self.hidden, self.packages, self.min_size, self.exclude)

    def excluded(self, path, name):
        return (bool(self.excl_names) and norm_name(name) in self.excl_names) or \
            (bool(self.excl_paths) and norm_name(path) in self.excl_paths)


# --- APFS klony: getattrlist(ATTR_CMNEXT_CLONEID | ATTR_CMNEXT_EXT_FLAGS)
_FSOPT_NOFOLLOW, _FSOPT_ATTR_CMN_EXTENDED = 0x1, 0x20
_ATTR_CMNEXT_CLONEID, _ATTR_CMNEXT_EXT_FLAGS = 0x100, 0x200
_EF_MAY_SHARE_BLOCKS = 0x1
_LIBC = None


class _AttrList(ctypes.Structure):
    _fields_ = [("bitmapcount", ctypes.c_ushort), ("reserved", ctypes.c_uint16),
                ("commonattr", ctypes.c_uint32), ("volattr", ctypes.c_uint32), ("dirattr", ctypes.c_uint32),
                ("fileattr", ctypes.c_uint32), ("forkattr", ctypes.c_uint32)]


def clone_id(path, dev=None):
    """Identifikátor dat APFS klonu, nebo None. Dva soubory se stejným identifikátorem jsou čisté
    klony – data mají na disku jen jednou. Používá se JEN pro zobrazení, nikdy k rozhodnutí o mazání."""
    global _LIBC
    if not IS_MAC:
        return None
    try:
        if _LIBC is None:
            lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            lib.getattrlist.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.c_size_t, ctypes.c_ulong]
            lib.getattrlist.restype = ctypes.c_int
            _LIBC = lib
        al = _AttrList(5, 0, 0, 0, 0, 0, _ATTR_CMNEXT_CLONEID | _ATTR_CMNEXT_EXT_FLAGS)
        buf = ctypes.create_string_buffer(64)
        if _LIBC.getattrlist(os.fsencode(path), ctypes.byref(al), buf, 64,
                             _FSOPT_NOFOLLOW | _FSOPT_ATTR_CMN_EXTENDED) != 0:
            return None
        length, cid, flags = struct.unpack_from("<IQQ", buf.raw)
        if length < 20 or not cid or not flags & _EF_MAY_SHARE_BLOCKS:
            return None
        return (dev if dev is not None else os.stat(path).st_dev, cid)
    except (OSError, AttributeError, struct.error):
        return None


def fill_clone_ids(groups, cancel=None):
    for g in groups:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        for f in g.files:
            f.clone = clone_id(f.path, f.dev)


def norm_name(name):
    """Názvy z macOS jsou v NFD – sjednotit + ignorovat velikost písmen (APFS je case-insensitive)."""
    return unicodedata.normalize("NFC", name).casefold()


def norm_search(text):
    """Pro hledání: bez diakritiky, bez velikosti písmen."""
    t = unicodedata.normalize("NFKD", text)
    return "".join(c for c in t if not unicodedata.combining(c)).casefold()


def scan_files(roots, opts, cancel=None, progress=None):
    """Projde složky a vrátí (seznam FileInfo, statistika). Symlinky se nesledují,
    pevné odkazy (stejný inode) se počítají jen jednou."""
    files, seen = [], set()
    stats = {"dirs": 0, "files": 0, "errors": 0, "hardlinks": 0, "skipped_small": 0}
    root_skip = SYSTEM_ROOT_SKIP if "/" in roots else set()
    last = 0.0
    for root in roots:
        root = os.path.abspath(root)
        if opts.excluded(root, os.path.basename(root)):
            stats["excluded"] = stats.get("excluded", 0) + 1
            continue
        stack = [root]
        while stack:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            d = stack.pop()
            try:
                it = os.scandir(d)
            except OSError:
                stats["errors"] += 1
                continue
            with it:
                for e in it:
                    name = e.name
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            if name in SKIP_DIR_NAMES:
                                continue
                            if not opts.hidden and name.startswith("."):
                                continue
                            if e.path in root_skip:
                                continue
                            if opts.excluded(e.path, name):
                                stats["excluded"] = stats.get("excluded", 0) + 1
                                continue
                            if not opts.packages and os.path.splitext(name)[1].lower() in PACKAGE_EXT:
                                continue
                            stack.append(e.path)
                            continue
                        if not e.is_file(follow_symlinks=False):
                            continue
                        if name in SKIP_FILE_NAMES or name.startswith("._"):
                            continue
                        if not opts.hidden and name.startswith("."):
                            continue
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        stats["errors"] += 1
                        continue
                    stats["files"] += 1
                    if st.st_size < opts.min_size:
                        stats["skipped_small"] += 1
                        continue
                    key = (st.st_dev, st.st_ino)
                    if key in seen:
                        stats["hardlinks"] += 1
                        continue
                    seen.add(key)
                    btime = getattr(st, "st_birthtime", None)
                    if btime is None:
                        btime = st.st_mtime
                    files.append(FileInfo(e.path, name, st.st_size, st.st_mtime, btime,
                                          st.st_dev, st.st_ino, root,
                                          bool(getattr(st, "st_flags", 0) & (0x2 | 0x20000)), st.st_ctime,
                                          bool(getattr(st, "st_flags", 0) & SF_DATALESS)))
            stats["dirs"] += 1
            if progress is not None:
                now = time.monotonic()
                if now - last > 0.15:
                    last = now
                    progress(T("Procházím… {0} složek, {1} souborů", fmt_int(stats['dirs']), fmt_int(stats['files'])),
                             None, d)
    return files, stats


def group_files(files, crit):
    """crit: dict s klíči name, size, mtime, btime, content (bool). Vrací seznam Group."""
    if not any(crit.get(k) for k in ("name", "size", "mtime", "btime", "content")):
        raise ValueError(T("Vyber aspoň jedno kritérium."))
    use_size = crit.get("size") or crit.get("content")
    buckets = {}
    for f in files:
        k = []
        if crit.get("name"):
            k.append(norm_name(f.name))
        if use_size:
            k.append(f.size)
        if crit.get("mtime"):
            k.append(int(f.mtime))
        if crit.get("btime"):
            k.append(int(f.btime))
        buckets.setdefault(tuple(k), []).append(f)
    return [Group(sorted(g, key=lambda x: x.path)) for g in buckets.values() if len(g) > 1]


def file_digest(path, partial=False, cancel=None, on_bytes=None):
    h = hashlib.blake2b(digest_size=20)
    with open(path, "rb") as fh:
        if partial:
            h.update(fh.read(CHUNK))
            size = os.fstat(fh.fileno()).st_size
            if size > 2 * CHUNK:
                fh.seek(-CHUNK, os.SEEK_END)
                h.update(fh.read(CHUNK))
            return h.digest()
        while True:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            b = fh.read(1 << 20)
            if not b:
                break
            h.update(b)
            if on_bytes:
                on_bytes(len(b))
    return h.digest()


def _split(files, keyfn):
    d = {}
    for f in files:
        try:
            k = keyfn(f)
        except OSError:
            continue
        d.setdefault(k, []).append(f)
    return [g for g in d.values() if len(g) > 1]


CACHE_FILE = os.path.join(SUPPORT_DIR, "otisky.sqlite")


class DigestCache:
    """Trvalá paměť otisků obsahu. Platí jen pro soubor se stejnou cestou, velikostí, datem změny
    i číslem inode – jakákoli změna = otisk se spočítá znovu. Používá se jen k NALEZENÍ shody;
    před každou akcí se soubory stejně porovnají bajt po bajtu."""

    def __init__(self, path=None):
        self.db, self.pending, self.hits, self.misses = None, 0, 0, 0
        path = path or CACHE_FILE
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.db = sqlite3.connect(path, timeout=10)
            self.db.execute("DROP TABLE IF EXISTS d")       # starší formát bez ctime
            self.db.execute("CREATE TABLE IF NOT EXISTS o (path TEXT, kind TEXT, size INTEGER, mtime REAL, "
                            "ino INTEGER, ctime REAL, dev INTEGER, digest BLOB, seen INTEGER, "
                            "PRIMARY KEY(path, kind))")
        except sqlite3.Error:
            self.db = None

    def get(self, f, kind):
        if self.db is None:
            return None
        try:
            row = self.db.execute("SELECT size, mtime, ino, ctime, dev, digest FROM o WHERE path=? AND kind=?",
                                  (f.path, kind)).fetchone()
        except sqlite3.Error:
            return None
        if row and row[:5] == (f.size, f.mtime, f.ino, f.ctime, f.dev) and f.ctime:
            self.hits += 1
            return bytes(row[5])
        self.misses += 1
        return None

    def put(self, f, kind, digest):
        if self.db is None:
            return
        try:
            self.db.execute("INSERT OR REPLACE INTO o VALUES (?,?,?,?,?,?,?,?,?)",
                            (f.path, kind, f.size, f.mtime, f.ino, f.ctime, f.dev, digest, int(time.time())))
            self.pending += 1
            if self.pending >= 500:
                self.db.commit()
                self.pending = 0
        except sqlite3.Error:
            pass

    def close(self):
        if self.db is None:
            return
        try:
            self.db.commit()
            n = self.db.execute("SELECT COUNT(*) FROM o").fetchone()[0]
            if n > 5_000_000:                  # nejvýš ~5 milionů záznamů – nejstarší pryč
                self.db.execute("DELETE FROM o WHERE rowid IN (SELECT rowid FROM o ORDER BY seen LIMIT ?)",
                                (n - 4_000_000,))
                self.db.commit()
            self.db.close()
        except sqlite3.Error:
            pass
        self.db = None


def clear_digest_cache():
    for suffix in ("", "-journal", "-wal", "-shm"):
        try:
            os.remove(CACHE_FILE + suffix)
        except OSError:
            pass


def _cached_digest(cache, f, partial, **kw):
    kind = "p" if partial else "f"
    if cache is not None:
        d = cache.get(f, kind)
        if d is not None:
            if not partial and kw.get("on_bytes"):
                kw["on_bytes"](f.size)
            return d
    d = file_digest(f.path, partial=partial, **kw)
    if cache is not None:
        cache.put(f, kind, d)
    return d


def verify_groups(groups, cancel=None, progress=None, cache=None, cloud_skipped=None):
    """Rozdělí skupiny podle skutečného obsahu: nejdřív rychlý otisk (začátek+konec),
    pak plný BLAKE2 hash. Výsledné skupiny mají verified=True.
    `cache` (DigestCache) – už spočítané otisky nezměněných souborů se nečtou znovu."""
    # soubory jen v cloudu (nestažené) nečíst – čtení by je celé stáhlo
    if cloud_skipped is not None:
        cloud_skipped.append(sum(1 for g in groups for f in g.files if f.dataless))
    groups = [g for g in (Group([f for f in g.files if not f.dataless]) for g in groups) if len(g.files) > 1]
    stage1 = []
    n = len(groups)
    last = 0.0
    for i, g in enumerate(groups):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        by_size = _split(g.files, lambda f: f.size)
        for sg in by_size:
            stage1.extend(_split(sg, lambda f: _cached_digest(cache, f, True)))
        now = time.monotonic()
        if progress and now - last > 0.15:
            last = now
            progress(T("Rychlé porovnání obsahu… {0}/{1} skupin", i + 1, n), (i + 1) / max(n, 1) * 0.2, None)
    total = sum(sum(f.size for f in g) for g in stage1 if g[0].size > CHUNK) or 1
    done = [0]
    state = {"last": 0.0}

    def on_bytes(k):
        done[0] += k
        now = time.monotonic()
        if progress and now - state["last"] > 0.15:
            state["last"] = now
            progress(T("Ověřuji obsah… {0} z {1}", fmt_size(done[0]), fmt_size(total)),
                     0.2 + 0.8 * done[0] / total, None)

    result = []
    for g in stage1:
        if g[0].size <= CHUNK:         # malý soubor = částečný otisk přečetl celý obsah
            result.append(Group(sorted(g, key=lambda x: x.path), verified=True))
            continue
        for sg in _split(g, lambda f: _cached_digest(cache, f, False, cancel=cancel, on_bytes=on_bytes)):
            result.append(Group(sorted(sg, key=lambda x: x.path), verified=True))
    return result


def _ident_chain(path):
    """(zařízení, inode) složky a všech nadřazených – odolné vůči symlinkům, /tmp vs /private/tmp
    i velikosti písmen v cestě."""
    p, out = os.path.realpath(path), []
    while True:
        try:
            st = os.stat(p)
            out.append((st.st_dev, st.st_ino))
        except OSError:
            pass
        parent = os.path.dirname(p)
        if parent == p:
            return out
        p = parent


def is_inside(path, folder):
    """Je `path` uvnitř `folder` (nebo totéž místo)?"""
    try:
        st = os.stat(folder)
    except OSError:
        return False
    return (st.st_dev, st.st_ino) in _ident_chain(path)


def paths_overlap(a, b):
    return is_inside(a, b) or is_inside(b, a)


_FOLDER_CACHE = {}


def in_folder(path, folder):
    """Je soubor ve složce? Bez ohledu na velikost písmen, zápis diakritiky (NFC/NFD) a symlinky ve složce."""
    nf = _FOLDER_CACHE.get(folder)
    if nf is None:
        if len(_FOLDER_CACHE) > 256:
            _FOLDER_CACHE.clear()
        nf = _FOLDER_CACHE[folder] = norm_name(os.path.realpath(folder)).rstrip("/") + "/"
    return norm_name(path).startswith(nf) or norm_name(os.path.abspath(path)).startswith(nf)


STRATEGIES = {
    T("Ponechat nejstarší (datum vytvoření)"): lambda f: (f.btime, f.mtime, len(f.path), f.path),
    T("Ponechat nejstarší (datum změny)"): lambda f: (f.mtime, f.btime, len(f.path), f.path),
    T("Ponechat nejnovější (datum změny)"): lambda f: (-f.mtime, -f.btime, len(f.path), f.path),
    T("Ponechat nejkratší cestu"): lambda f: (len(f.path), f.path),
    T("Ponechat nejdelší cestu"): lambda f: (-len(f.path), f.path),
    T("Ponechat soubor ve vybrané složce…"): None,       # řeší GUI (zeptá se na složku)
}


def auto_mark(groups, strategy, prefer_folder=None):
    """V každé skupině ponechá jeden soubor podle strategie, ostatní označí."""
    keyfn = STRATEGIES.get(strategy) or STRATEGIES[T("Ponechat nejstarší (datum vytvoření)")]
    count = 0
    for g in groups:
        if g.merged:                    # už sloučeno klonem – nic dalšího neušetří
            continue
        if prefer_folder:
            inside = [f for f in g.files if in_folder(f.path, prefer_folder)]
            if not inside:              # skupina nemá žádný soubor ve složce → nechat beze změny
                continue
            keep = sorted(inside, key=keyfn)[0]
        else:
            keep = sorted(g.files, key=keyfn)[0]
        for f in g.files:
            f.marked = f is not keep and not in_package(f)
            count += f.marked
    return count


def auto_mark_per_volume(groups, strategy):
    """Pro „Uvolnit místo“: ponechaný soubor se vybere ZVLÁŠŤ na každém disku (klon jde jen v rámci
    jednoho svazku). Soubory, které už jsou klonem ponechaného, se neoznačí. Vrací (počet, úspora)."""
    keyfn = STRATEGIES.get(strategy) or STRATEGIES[T("Ponechat nejstarší (datum vytvoření)")]
    count = save = 0
    for g in groups:
        if g.merged:
            continue
        by_dev = {}
        for f in g.files:
            by_dev.setdefault(f.dev, []).append(f)
        for sub in by_dev.values():
            sub = [f for f in sub if not is_cloud(f.path) and not f.dataless]   # cloud se klonovat nesmí
            if len(sub) < 2:
                continue
            keep = sorted(sub, key=keyfn)[0]
            for f in sub:
                if f is not keep and not in_package(f) and not (f.clone and f.clone == keep.clone):
                    f.marked = True
                    count += 1
                    save += f.size
    return count, save


def mark_in_folder(groups, folder, mark=True):
    """Označí soubory v dané složce – ale nikdy ne všechny soubory skupiny."""
    count = 0
    for g in groups:
        if mark and g.merged:           # už sloučeno klonem – nic by se neušetřilo
            continue
        unmarked = sum(1 for x in g.files if not x.marked)
        for f in g.files:
            if in_folder(f.path, folder):
                if mark and in_package(f):
                    continue
                if mark and not f.marked and unmarked <= 1:
                    break
                if f.marked != mark:
                    f.marked = mark
                    unmarked += -1 if mark else 1
                    count += 1
    return count


def plan_actions(groups):
    """Vrátí [([ponechané], [označené])] – jen skupiny, kde aspoň jeden soubor zůstává.
    Soubory uvnitř balíčků/skrytých složek se nikdy neodstraňují."""
    plan, skipped = [], 0
    for g in groups:
        marked = [f for f in g.files if f.marked and not in_package(f)]
        keep = [f for f in g.files if not f.marked]
        if not marked:
            continue
        if not keep:
            skipped += 1
            continue
        plan.append((keep, marked))
    return plan, skipped


# ---------------- akce se soubory ----------------

def _log(action, src, dst="", note=""):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        fn = os.path.join(LOG_DIR, datetime.date.today().strftime("akce-%Y-%m.log"))
        with open(fn, "a", encoding="utf-8") as fh:
            fh.write("\t".join([datetime.datetime.now().isoformat(timespec="seconds"),
                                action, src, dst, note]) + "\n")
    except OSError:
        pass


def _log_many(rows):
    """Více záznamů najednou (jedno otevření souboru)."""
    if not rows:
        return
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        fn = os.path.join(LOG_DIR, datetime.date.today().strftime("akce-%Y-%m.log"))
        now = datetime.datetime.now().isoformat(timespec="seconds")
        with open(fn, "a", encoding="utf-8") as fh:
            fh.writelines("\t".join([now, a, str(src), dst, note.replace("\n", " ")]) + "\n"
                          for a, src, dst, note in rows)
    except OSError:
        pass


_TRASH_SCRIPT = '''on run argv
  set L to {}
  repeat with p in argv
    set end of L to (POSIX file (p as text))
  end repeat
  tell application "Finder" to delete L
end run'''

_ALIAS_SCRIPT = '''on run argv
  set tgt to (POSIX file (item 1 of argv)) as alias
  set dirp to (POSIX file (item 2 of argv)) as alias
  tell application "Finder"
    set a to make new alias file at dirp to tgt
    set name of a to (item 3 of argv)
  end tell
end run'''


def trash_paths(paths):
    """Přesune do Koše (jde vrátit: Koš → pravé tlačítko → Vrátit zpět). Vrací (ok, chyby)."""
    paths = list(paths)
    if not paths:
        return [], []
    net = [p for p in paths if is_network(p) or (IS_MAC and not fs_type(p))]
    paths = [p for p in paths if p not in set(net)]
    for i in range(0, len(paths), 200):
        part = paths[i:i + 200]
        if os.path.exists("/usr/bin/trash"):
            subprocess.run(["/usr/bin/trash", *part], capture_output=True)
            if any(os.path.lexists(p) for p in part) and IS_MAC:   # zkusit ještě přes Finder
                rest = [p for p in part if os.path.lexists(p)]
                subprocess.run(["/usr/bin/osascript", "-e", _TRASH_SCRIPT, *rest], capture_output=True)
        elif IS_MAC:
            subprocess.run(["/usr/bin/osascript", "-e", _TRASH_SCRIPT, *part], capture_output=True)
    ok, err = [], [(p, Skip(T("síťový nebo neznámý disk – Koš tam nemusí být (soubor by se smazal hned); použij Přesunout do…"))) for p in net]
    for p in paths:
        if os.path.lexists(p):
            err.append((p, T("nepodařilo se přesunout do Koše")))
        else:
            ok.append(p)
            _log("KOS", p)
    return ok, err


# ---------------- zamčené soubory a chybějící oprávnění ----------------

UF_IMMUTABLE = getattr(stat, "UF_IMMUTABLE", 0x2)      # Finder → Informace → „Zamčeno“
UF_APPEND = getattr(stat, "UF_APPEND", 0x4)
SF_IMMUTABLE = getattr(stat, "SF_IMMUTABLE", 0x20000)  # systémový zámek (jen správce)
SF_APPEND = getattr(stat, "SF_APPEND", 0x40000)
USER_LOCK = UF_IMMUTABLE | UF_APPEND
SYS_LOCK = SF_IMMUTABLE | SF_APPEND
PROTECTED_PREFIXES = ("/System/", "/bin/", "/sbin/", "/usr/", "/private/var/db/")

# kódy příčin → (popis do přehledu, co s tím)
CAUSES = {
    "locked":    (T("🔒 Zamčený soubor"), "user"),       # uživatel ho může odemknout sám
    "locked_dir": (T("🔒 Zamčená složka"), "user"),
    "locked_other": (T("🔒 Zamčený soubor jiného uživatele"), "admin"),
    "sys_locked": (T("🔒 Systémový zámek"), "admin"),
    "dir_perm":  (T("👤 Bez oprávnění zapisovat do složky"), "admin"),
    "sticky":    (T("👤 Soubor jiného uživatele ve sdílené složce"), "admin"),
    "acl":       (T("👤 Zakázáno pravidlem ACL"), "admin"),
    "no_read":   (T("👤 Bez oprávnění soubor číst"), "perm"),
    "tcc":       (T("🛡 macOS nepovolil přístup (Plný přístup k disku)"), "tcc"),
    "ro":        (T("⛔ Disk je jen pro čtení"), "none"),
    "sip":       (T("⛔ Chráněno systémem macOS"), "none"),
    "missing":   (T("Soubor už neexistuje"), "none"),
    "other":     (T("Jiná chyba"), "none"),
    "skipped":   (T("🛡 Přeskočeno ochranou"), "none"),
    "undiag":    (T("Další chyby (podrobně nerozebrány)"), "none"),
}


def _owner(uid):
    try:
        import pwd
        return pwd.getpwuid(uid).pw_name
    except (ImportError, KeyError):
        return str(uid)


_ACL_CACHE = {}


def _acl_denies(path, words):
    key = (path, words)
    if key not in _ACL_CACHE:
        if len(_ACL_CACHE) > 5000:
            _ACL_CACHE.clear()
        _ACL_CACHE[key] = _acl_denies_raw(path, words)
    return _ACL_CACHE[key]


def _acl_denies_raw(path, words):
    if not IS_MAC:
        return False
    try:
        out = subprocess.run(["/bin/ls", "-lde", path], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return any("deny" in ln and any(w in ln for w in words) for ln in out.splitlines()[1:])


def diagnose(path, msg="", need_read=False):
    """Zjistí, proč soubor nejde smazat/přesunout/nahradit. Vrací [(kód, podrobnost)]."""
    if isinstance(msg, Skip):
        return [("skipped", str(msg))]

    if not os.path.lexists(path):
        return [("missing", "")]
    uid = os.getuid()
    parent = os.path.dirname(path) or "/"
    out = []
    real = os.path.realpath(path)
    if real.startswith(PROTECTED_PREFIXES) and not real.startswith("/usr/local/"):
        out.append(("sip", ""))
    try:
        if os.statvfs(parent).f_flag & os.ST_RDONLY:
            return out + [("ro", T("např. disk NTFS z Windows nebo zamčená SD karta"))]
    except OSError:
        pass
    try:
        st, pst = os.lstat(path), os.stat(parent)
    except OSError as exc:
        return out + [("tcc" if "not permitted" in str(exc) else "other", str(exc))]
    flags, pflags = getattr(st, "st_flags", 0), getattr(pst, "st_flags", 0)
    if flags & USER_LOCK:
        out.append(("locked", "") if st.st_uid == uid else ("locked_other", T("vlastník: {0}", _owner(st.st_uid))))
    if flags & SYS_LOCK or pflags & SYS_LOCK:
        out.append(("sys_locked", ""))
    if pflags & USER_LOCK:
        out.append(("locked_dir", os.path.basename(parent)) if pst.st_uid == uid
                   else ("locked_other", T("složka {0}, vlastník: {1}", os.path.basename(parent), _owner(pst.st_uid))))
    elif not os.access(parent, os.W_OK | os.X_OK):
        out.append(("dir_perm", T("složka „{0}“ patří: {1}", os.path.basename(parent) or parent, _owner(pst.st_uid))))
    elif pst.st_mode & stat.S_ISVTX and st.st_uid != uid and pst.st_uid != uid:
        out.append(("sticky", T("vlastník souboru: {0}", _owner(st.st_uid))))
    if _acl_denies(parent, ("delete_child",)) or _acl_denies(path, ("delete",)):
        out.append(("acl", ""))
    if (need_read or isinstance(msg, PermMsg)) and not os.access(path, os.R_OK):
        out.append(("no_read", T("vlastník: {0}", _owner(st.st_uid))))
    if not out:
        out.append(("tcc", "") if "not permitted" in msg else ("other", msg))
    return out


def diagnose_errors(errors, need_read=False):
    """[(cesta, zpráva)] → [(cesta, zpráva, [(kód, podrobnost)])]
    Podrobně se rozebere nejvýš 500 chyb (u statisíců by to trvalo hodiny)."""
    _ACL_CACHE.clear()
    out, by_dir, by_msg, n = [], {}, {}, 0
    for p, m in errors:
        if not p:
            out.append((p, m, [("other", m)]))
        elif isinstance(m, Skip):
            out.append((p, m, [("skipped", str(m))]))
        elif n < 500:
            n += 1
            c = diagnose(p, m, need_read)
            by_dir.setdefault(os.path.dirname(p), c)
            by_msg.setdefault(str(m), c)
            out.append((p, m, c))
        else:   # další chyby: stejná příčina jako u souboru ze stejné složky / se stejnou zprávou
            c = by_dir.get(os.path.dirname(p)) or by_msg.get(str(m))
            out.append((p, m, c if c else [("undiag", m)]))
    return out


def fix_class(causes):
    """Co je potřeba: 'user' (odemknout sám), 'admin' (heslo správce), 'perm' (opravit práva ve složce),
    'tcc', 'none'."""
    kinds = {CAUSES[c][1] for c, _ in causes}
    if "none" in kinds:
        return "none"
    if "tcc" in kinds:
        return "tcc"
    if "perm" in kinds:
        return "perm"
    if "admin" in kinds:
        return "admin"
    return "user"


def unlock_user(paths):
    """Odemkne zamčené soubory (a jejich složky), které patří přihlášenému uživateli.
    Vrací seznam [(cesta, původní příznaky)] pro pozdější zamknutí zpět."""
    uid, undo, seen = os.getuid(), [], set()
    for p in paths:
        for q in (p, os.path.dirname(p)):
            if q in seen:
                continue
            seen.add(q)
            try:
                st = os.lstat(q)
                fl = getattr(st, "st_flags", 0)
                if fl & USER_LOCK and st.st_uid == uid:
                    (os.lchflags if hasattr(os, "lchflags") else os.chflags)(q, fl & ~USER_LOCK)
                    undo.append((q, fl))
                    _log("ODEMCENO", q)
            except (OSError, AttributeError):
                pass
    return undo


def relock(undo, only_dirs=False):
    for p, fl in undo:
        if only_dirs and not os.path.isdir(p):
            continue
        try:
            if os.path.lexists(p):
                os.chflags(p, fl)
                _log("ZAMCENO_ZPET", p)
        except (OSError, AttributeError):
            pass


_ADMIN_SH = r'''#!/bin/bash
# Spouští se s právy správce: přesune dvojice zdroj→cíl ze seznamu (oddělené \0),
# před přesunem zruší zámek souboru, cíl předá přihlášenému uživateli. Nic nemaže.
LIST="$1"; U="$2"; G="$3"
while IFS= read -r -d '' src && IFS= read -r -d '' dst; do
  pd=$(dirname "$src")
  pf=$(stat -f '%Of' "$pd" 2>/dev/null)
  chflags -h nouchg,noschg,nouappnd,nosappnd "$src" 2>/dev/null
  chflags nouchg "$pd" 2>/dev/null
  d=$(dirname "$dst")
  if [ ! -d "$d" ]; then mkdir -p "$d" && chown "$U:$G" "$d" "$(dirname "$d")"; fi
  if [ ! -e "$dst" ] && [ ! -L "$dst" ]; then
    mv "$src" "$dst" && chown -Rh "$U:$G" "$dst"
  fi
  [ -n "$pf" ] && chflags "$pf" "$pd" 2>/dev/null
done < "$LIST"
exit 0
'''

_ADMIN_OSA = '''on run argv
  do shell script "/bin/bash " & quoted form of (item 1 of argv) & " " & quoted form of (item 2 of argv) & " " & (item 3 of argv) & " " & (item 4 of argv) with prompt (item 5 of argv) with administrator privileges
end run'''


class AdminCancelled(Exception):
    pass


def admin_move(pairs, prompt):
    """Přesune soubory s právy správce (macOS se zeptá na heslo). pairs = [(zdroj, cíl)].
    Vrací [(zdroj, cíl)] skutečně přesunutých."""
    if not pairs:
        return []
    work = tempfile.mkdtemp(prefix="dupl-admin-")
    r = None
    try:
        sh, lst = os.path.join(work, "presun.sh"), os.path.join(work, "seznam")
        with open(sh, "w") as fh:
            fh.write(_ADMIN_SH)
        with open(lst, "wb") as fh:
            for s, d in pairs:
                fh.write(os.fsencode(s) + b"\0" + os.fsencode(d) + b"\0")
        if IS_MAC:
            r = subprocess.run(["/usr/bin/osascript", "-e", _ADMIN_OSA, sh, lst, str(os.getuid()),
                                str(os.getgid()), prompt], capture_output=True, text=True)
        else:                                      # testy mimo macOS: už běžíme s potřebnými právy
            r = subprocess.run(["/bin/bash", sh, lst, str(os.getuid()), str(os.getgid())],
                               capture_output=True, text=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    done = [(s, d) for s, d in pairs if not os.path.lexists(s) and os.path.lexists(d)]
    for s, d in done:
        _log("PRESUN_SPRAVCE", s, d)
    if (r is None or r.returncode != 0) and not done:
        if r and ("-128" in r.stderr or "canceled" in r.stderr.lower() or "zrušil" in r.stderr.lower()):
            raise AdminCancelled()
        raise OSError((r.stderr.strip() if r else "") or T("akce s právy správce selhala"))
    return done


def _mount_point(path):
    p = os.path.abspath(os.path.dirname(path))
    while not os.path.ismount(p):
        p = os.path.dirname(p)
    return p


def staging_dir(path):
    """Pomocná složka na stejném disku, odkud už soubor jde dát do Koše bez hesla."""
    home = os.path.expanduser("~")
    try:
        same = os.stat(home).st_dev == os.stat(os.path.dirname(path)).st_dev
    except OSError:
        same = False
    if same:
        return os.path.join(SUPPORT_DIR, "Ke smazani")
    return os.path.join(_mount_point(path), ".DuplicitniSoubory-ke-smazani")


def admin_trash(paths, prompt):
    """Soubory bez oprávnění: správce je přesune do pomocné složky na stejném disku
    a předá uživateli, odtud jdou běžně do Koše. Vrací (ok, chyby)."""
    pairs = []
    for p in paths:
        d = os.path.join(staging_dir(p), uuid.uuid4().hex[:10], os.path.basename(p))
        try:
            os.makedirs(os.path.dirname(d), exist_ok=True)
        except OSError:
            pass                                   # vytvoří ji skript správce
        pairs.append((p, d))
    moved = admin_move(pairs, prompt)
    staged = {d: s for s, d in moved}
    ok_staged, _ = trash_paths(list(staged))
    ok = [staged[d] for d in ok_staged]
    err = []
    for s, d in pairs:
        if s in ok:
            _log("KOS", s, "", T("s právy správce"))
        elif (s, d) in moved:
            err.append((s, T("je v pomocné složce „{0}“ (nedostal se do Koše) – nic se neztratilo", os.path.dirname(d))))
        else:
            err.append((s, T("nepodařilo se ani s právy správce")))
        try:
            os.rmdir(os.path.dirname(d))
            os.rmdir(os.path.dirname(os.path.dirname(d)))
        except OSError:
            pass
    return ok, err


FDA_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"


# ---------------- hromadné odemčení a oprava práv ve složce ----------------

UNDO_DIR = os.path.join(SUPPORT_DIR, "Opravy prav")
ALL_LOCKS = USER_LOCK | SYS_LOCK
TM_MARKERS = ("Backups.backupdb", ".backupbundle", ".sparsebundle", "/.timemachine/", "com.apple.TimeMachine")


def perms_forbidden(path):
    """Kam opravu práv nepustit (systém, celé domovské složky, zálohy). Vrací důvod nebo None."""
    real = os.path.realpath(path)
    home = os.path.realpath(os.path.expanduser("~"))
    if real in ("/", "/Volumes", "/Users", "/System/Volumes/Data"):
        return T("celý systémový disk upravovat nelze – vyber konkrétní složku nebo externí disk")
    if os.path.dirname(real) == "/Users" or real == home:
        return T("celou domovskou složku upravovat nelze – vyber v ní konkrétní podsložku")
    for pre in ("/System", "/Library", "/Applications", "/usr", "/bin", "/sbin", "/private", "/opt",
                "/cores", os.path.join(home, "Library")):
        if real == pre or real.startswith(pre + "/"):
            return T("složka „{0}“ patří systému nebo aplikacím – její práva se nesmí měnit", pre)
    if any(m in real + "/" for m in TM_MARKERS):
        return T("zálohy Time Machine se upravovat nesmí")
    if real.startswith("/Volumes/"):
        vol = "/".join(real.split("/")[:3])
        has = lambda *p: os.path.exists(os.path.join(vol, *p))
        if has("Backups.backupdb"):
            return T("disk obsahuje zálohy Time Machine")
        mac_like = has("System", "Library", "CoreServices", "SystemVersion.plist") or \
            (has("Users") and has("Library") and (has("private") or has("System")))
        if mac_like:                           # jiný Mac / klon / datový svazek: jen datové podsložky
            rel = real[len(vol):].strip("/").split("/") if real != vol else []
            if not rel:
                return T("na disku je macOS (nebo jeho data) – vyber v něm konkrétní složku s daty")
            if rel[0] in ("System", "Library", "private", "usr", "bin", "sbin", "Applications", "cores", "opt"):
                return T("složka „{0}“ patří systému – její práva se nesmí měnit", rel[0])
            if rel[0] == "Users" and (len(rel) <= 2 or rel[2] == "Library"):
                return T("celou domovskou složku ani její Library upravovat nelze – vyber konkrétní podsložku")
    return None


def volume_info(path):
    """(typ souborového systému, ignoruje vlastníky?) podle výpisu `mount`."""
    if not IS_MAC:
        return "", False
    try:
        out = subprocess.run(["/sbin/mount"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return "", False
    real = os.path.realpath(path)
    mounts = {}
    for ln in out.splitlines():
        if " on " in ln and ln.endswith(")"):
            left, _, rest = ln.partition(" on ")
            mp, _, opts = rest.rpartition(" (")
            mounts[mp] = [o.strip() for o in opts[:-1].split(",")]
    best = max((mp for mp in mounts if real == mp or real.startswith(mp.rstrip("/") + "/")), key=len, default="/")
    if best == "/" and "/System/Volumes/Data" in mounts:
        best = "/System/Volumes/Data"
    opts = mounts.get(best, [""])
    return opts[0], "noowners" in opts


class PermOptions:
    def __init__(self, unlock=True, own=True, mode=True, acl=False):
        self.unlock, self.own, self.mode, self.acl = unlock, own, mode, acl


class PermScan:
    def __init__(self, root):
        self.root = root
        self.items = 0
        self.records = []       # [(cesta, je_složka, uid, gid, mode, flags, oprava_zámku, oprava_vlastníka, oprava_práv)]
        self.unreadable = []    # složky, do kterých nejde nahlédnout
        self.locked = self.sys_locked = self.foreign = self.no_rights = 0
        self.needs_admin = False
        self.fstype, self.noowners = "", False

    @property
    def problems(self):
        return len(self.records) + len(self.unreadable)


def perm_scan(root, opts, cancel=None, progress=None):
    """Zjistí, co je ve složce zamčené, cizí nebo bez práv. Nic nemění."""
    me, root = os.getuid(), os.path.abspath(root)
    res = PermScan(root)
    res.fstype, res.noowners = volume_info(root)
    rst = os.lstat(root)
    dev = rst.st_dev
    last = 0.0

    def check(path, st, is_dir):
        fl = getattr(st, "st_flags", 0)
        fix_fl = bool(opts.unlock and fl & ALL_LOCKS)
        # soubor s více pevnými odkazy může mít jména i mimo vybranou složku → vlastníka neměnit
        fix_own = bool(opts.own and not res.noowners and st.st_uid != me and (is_dir or st.st_nlink == 1))
        need = 0o700 if is_dir else 0o600
        fix_mode = bool(opts.mode and (st.st_mode & need) != need)
        if fl & USER_LOCK:
            res.locked += 1
        if fl & SYS_LOCK:
            res.sys_locked += 1
        if st.st_uid != me and not res.noowners:
            res.foreign += 1
        if (st.st_mode & need) != need:
            res.no_rights += 1
        if fix_fl or fix_own or fix_mode:
            res.records.append((path, is_dir, st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode), fl,
                                fix_fl, fix_own, fix_mode))
            if fix_own or fl & SYS_LOCK or (st.st_uid != me and not res.noowners):
                res.needs_admin = True

    if not os.path.ismount(root):
        check(root, rst, True)
    stack = [root]
    while stack:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            res.unreadable.append(d)
            res.needs_admin = res.needs_admin or os.lstat(d).st_uid != me
            continue
        with it:
            for e in it:
                if e.name in SKIP_DIR_NAMES or e.name == "Backups.backupdb" \
                        or e.name.endswith((".backupbundle", ".sparsebundle")):
                    continue
                try:
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISLNK(st.st_mode) or st.st_dev != dev:
                    continue
                res.items += 1
                is_dir = stat.S_ISDIR(st.st_mode)
                check(e.path, st, is_dir)
                if is_dir:
                    stack.append(e.path)
        if progress is not None:
            now = time.monotonic()
            if now - last > 0.15:
                last = now
                progress(T("Kontroluji… {0} položek", fmt_int(res.items)), None, d)
    return res


def _save_undo(root, rows):
    """Uloží původní vlastníky/práva/zámky, aby šla oprava vrátit."""
    os.makedirs(UNDO_DIR, exist_ok=True)
    fn = os.path.join(UNDO_DIR, datetime.datetime.now().strftime("%Y-%m-%d %H.%M.%S.%f") + ".jsonl")
    with open(fn, "x", encoding="utf-8") as fh:        # "x" = nikdy nepřepsat jiný záznam
        fh.write(json.dumps({"root": root}, ensure_ascii=False) + "\n")
        for r in rows:
            fh.write(json.dumps(list(r), ensure_ascii=False) + "\n")
    return fn


def last_undo():
    """(soubor, kořenová složka, počet položek) poslední opravy, nebo None."""
    try:
        files = sorted(f for f in os.listdir(UNDO_DIR) if f.endswith(".jsonl"))
    except OSError:
        return None
    for name in reversed(files):               # poškozený / prázdný záznam přeskočit
        fn = os.path.join(UNDO_DIR, name)
        try:
            with open(fn, encoding="utf-8") as fh:
                root = json.loads(fh.readline()).get("root", "?")
                n = sum(1 for _ in fh)
            return fn, root, n
        except (OSError, ValueError, AttributeError):
            continue
    return None


_PERMS_SH = r'''#!/bin/bash
# Spouští se s právy správce. Seznamy cest jsou oddělené \0. Nic nemaže.
D="$1"; U="$2"; G="$3"; ROOT="$4"; ACL="$5"; OWN="$6"; MODE="$7"; UNLOCK="$8"
[ -s "$D/flags" ] && xargs -0 chflags -h nouchg,nouappnd,noschg,nosappnd < "$D/flags"
[ -s "$D/own" ]   && xargs -0 chown -h "$U:$G" < "$D/own"
[ -s "$D/fmode" ] && xargs -0 chmod u+rw < "$D/fmode"
[ -s "$D/dmode" ] && xargs -0 chmod u+rwx < "$D/dmode"
if [ -s "$D/rec" ]; then
  # obsah nepřístupných složek: nejdřív zapsat původní stav (pro vrácení), pak opravit
  # -x: nepřecházet na jiné připojené disky
  xargs -0 -I{} find -x {} -mindepth 1 ! -type l -print0 < "$D/rec" > "$D/rec_all"
  xargs -0 stat -f $'%N\t%u\t%g\t%Op\t%Of' < "$D/rec_all" > "$D/rec_undo" 2>/dev/null
  chown "$U" "$D/rec_undo"
  if [ -s "$D/rec_all" ]; then
    [ "$UNLOCK" = 1 ] && xargs -0 chflags -h nouchg,nouappnd,noschg,nosappnd < "$D/rec_all"
    # vlastníka měnit jen u složek a souborů bez dalších pevných odkazů (mohou být i mimo složku)
    [ "$OWN" = 1 ] && xargs -0 -I{} find -x {} -mindepth 1 \( -type d -o -links 1 \) ! -type l -print0 < "$D/rec" \
                   | xargs -0 chown -h "$U:$G"
    [ "$MODE" = 1 ]   && xargs -0 chmod u+rwX < "$D/rec_all"
  fi
fi
[ "$ACL" = 1 ] && find -x "$ROOT" -mindepth 1 ! -type l -print0 | xargs -0 chmod -N 2>/dev/null
exit 0
'''

_RESTORE_SH = r'''#!/bin/bash
# Vrátí vlastníka, práva a zámky podle seznamu (cesta\0uid\0gid\0mode\0flags\0).
while IFS= read -r -d '' p && IFS= read -r -d '' u && IFS= read -r -d '' g \
      && IFS= read -r -d '' m && IFS= read -r -d '' f; do
  [ -e "$p" ] || continue
  chflags -h 0 "$p" 2>/dev/null
  chown -h "$u:$g" "$p" 2>/dev/null
  chmod "$m" "$p" 2>/dev/null
  chflags -h "$f" "$p" 2>/dev/null
done < "$1"
exit 0
'''


def _run_admin_script(script, args, prompt, files):
    """Spustí skript s právy správce. files = {název: bajty} se zapíší do pracovní složky (1. argument)."""
    work = tempfile.mkdtemp(prefix="dupl-prava-")
    try:
        for name, data in files.items():
            with open(os.path.join(work, name), "wb") as fh:
                fh.write(data)
        sh = os.path.join(work, "skript.sh")
        with open(sh, "w") as fh:
            fh.write(script)
        argv = [work] + [str(a) for a in args]
        if IS_MAC:
            quoted = " & \" \" & ".join(f"quoted form of (item {i + 2} of argv)" for i in range(len(argv)))
            osa = (f'on run argv\n do shell script "/bin/bash " & quoted form of (item 1 of argv) & " " & {quoted} '
                   f'with prompt (item {len(argv) + 2} of argv) with administrator privileges\nend run')
            r = subprocess.run(["/usr/bin/osascript", "-e", osa, sh, *argv, prompt], capture_output=True, text=True)
        else:                                      # testy mimo macOS
            r = subprocess.run(["/bin/bash", sh, *argv], capture_output=True, text=True)
        if r.returncode != 0:
            if "-128" in r.stderr or "canceled" in r.stderr.lower() or "zrušil" in r.stderr.lower():
                raise AdminCancelled()
            raise OSError(r.stderr.strip() or T("akce s právy správce selhala"))
        out = {}
        for name in os.listdir(work):
            with open(os.path.join(work, name), "rb") as fh:
                out[name] = fh.read()
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _z(paths):
    return b"".join(os.fsencode(p) + b"\0" for p in paths)


def perm_fix(scan, opts, prompt="", cancel=None, progress=None):
    """Provede opravu podle náhledu. Vrací (soubor pro vrácení, počet chyb)."""
    rows = [(r[0], r[2], r[3], r[4], r[5]) for r in scan.records]
    errors = 0
    undo = _save_undo(scan.root, rows) if rows or scan.unreadable else None   # uložit DŘÍV, než se cokoli změní
    if scan.needs_admin or scan.unreadable:
        files = {
            "flags": _z(r[0] for r in scan.records if r[6]),
            "own": _z(r[0] for r in scan.records if r[7]),
            "fmode": _z(r[0] for r in scan.records if r[8] and not r[1]),
            "dmode": _z(r[0] for r in scan.records if r[8] and r[1]),
            "rec": _z(scan.unreadable),
        }
        if progress:
            progress(T("Čekám na heslo správce…"), None, None)
        extra = []
        out = _run_admin_script(_PERMS_SH, [os.getuid(), os.getgid(), scan.root, int(opts.acl), int(opts.own),
                                            int(opts.mode), int(opts.unlock)], prompt, files)
        for ln in out.get("rec_undo", b"").decode("utf-8", "replace").splitlines():
            parts = ln.split("\t")
            if len(parts) == 5:
                try:
                    extra.append((parts[0], int(parts[1]), int(parts[2]), int(parts[3], 8) & 0o7777,
                                  int(parts[4], 8)))
                except ValueError:
                    pass
        if extra and undo:
            with open(undo, "a", encoding="utf-8") as fh:
                for r in extra:
                    fh.write(json.dumps(list(r), ensure_ascii=False) + "\n")
            rows += extra
    else:
        # vše patří přihlášenému uživateli → bez hesla; nepřístupné vlastní složky se opraví a projdou znovu
        pending = list(scan.records)
        n = len(pending)
        for i, (p, is_dir, uid, gid, mode, fl, fix_fl, fix_own, fix_mode) in enumerate(pending, 1):
            if cancel is not None and cancel.is_set():
                break
            if progress and i % 200 == 1:
                progress(T("Opravuji… {0}/{1}", fmt_int(i), fmt_int(n)), i / n, p)
            try:
                if fix_fl:
                    (os.lchflags if hasattr(os, "lchflags") else os.chflags)(p, fl & ~ALL_LOCKS)
                if fix_mode:
                    os.chmod(p, mode | (0o700 if is_dir else 0o600))
            except OSError:
                errors += 1
        if opts.acl and IS_MAC:
            subprocess.run(f"find -x {_shq(scan.root)} -mindepth 1 ! -type l -print0 | xargs -0 chmod -N",
                           shell=True, capture_output=True)
    _log("OPRAVA_PRAV", scan.root, undo or "", T("{0} položek", len(rows)))
    return undo, errors


def _shq(s):
    return "'" + s.replace("'", "'\\''") + "'"


def perm_restore(undo_file, prompt=""):
    """Vrátí opravu podle uloženého záznamu. Vrací počet položek."""
    rows = []
    with open(undo_file, encoding="utf-8") as fh:
        root = json.loads(fh.readline()).get("root", "")
        for ln in fh:
            try:
                rows.append(json.loads(ln))
            except ValueError:
                pass
    me = os.getuid()
    if all(r[1] == me and not r[4] & SYS_LOCK for r in rows):
        for p, uid, gid, mode, fl in rows:
            try:
                if os.path.lexists(p):
                    if hasattr(os, "lchflags"):
                        os.lchflags(p, 0)
                    os.chmod(p, mode)
                    if hasattr(os, "lchflags"):
                        os.lchflags(p, fl)
            except OSError:
                pass
    else:
        data = b"".join(os.fsencode(p) + b"\0" + b"\0".join(str(x).encode() for x in (u, g, oct(m)[2:], oct(f)[2:]))
                        + b"\0" for p, u, g, m, f in rows)
        _run_admin_script(_RESTORE_SH.replace('"$1"', '"$1/seznam"'), [], prompt, {"seznam": data})
    os.rename(undo_file, undo_file[:-6] + " (vraceno).txt")
    _log("VRACENI_PRAV", root, undo_file, T("{0} položek", len(rows)))
    return len(rows)




# ---------------- bezpečnostní kontrola před každou akcí ----------------
#  Zásada: soubor se smaže/přesune/nahradí JEN tehdy, když existuje ponechaný soubor,
#  který jde celý přečíst a je s ním bajt po bajtu shodný (včetně resource forku).
#  Poškozený nebo nečitelný originál = nic se nestane.

NETWORK_FS = {"smbfs", "afpfs", "nfs", "webdav", "cifs", "ftp", "fusefs", "macfuse", "osxfuse", "dfsfuse_dfs"}
_FS_CACHE = {}


def fs_type(path):
    try:
        dev = os.stat(os.path.dirname(path) or path).st_dev
    except OSError:
        return ""
    if dev in _FS_CACHE:
        return _FS_CACHE[dev]
    t = volume_info(path)[0]
    if t:
        _FS_CACHE[dev] = t
    return t


def is_network(path):
    return fs_type(path).lower() in NETWORK_FS


def in_package(f):
    """Soubor uvnitř balíčku (.app, knihovna Fotek…) nebo skryté složky (.git…)?
    Takový soubor se nesmí mazat – rozbila by se celá knihovna. Smí být jen ponechaný."""
    rel = os.path.relpath(f.path, f.root)
    for comp in rel.split(os.sep)[:-1]:
        if comp.startswith(".") or os.path.splitext(comp)[1].lower() in PACKAGE_EXT:
            return True
    return False


def _rsrc(path):
    return os.path.join(path, "..namedfork", "rsrc")


def rsrc_same(a, b):
    """Shodný resource fork (starší Mac soubory v něm mají data)? Mimo macOS vždy True."""
    if not IS_MAC:
        return True
    try:
        sa = os.path.getsize(_rsrc(a))
    except OSError:
        sa = 0
    try:
        sb = os.path.getsize(_rsrc(b))
    except OSError:
        sb = 0
    if sa != sb:
        return False
    if sa == 0:
        return True
    filecmp.clear_cache()
    return filecmp.cmp(_rsrc(a), _rsrc(b), shallow=False)


USER_META_XATTRS = ("com.apple.metadata:_kMDItemUserTags", "com.apple.metadata:kMDItemFinderComment")


class Skip(str):
    """Důvod, proč aplikace soubor ZÁMĚRNĚ nezpracovala (ochrana dat) – nejde o chybu oprávnění."""


class PermMsg(str):
    """Soubor/složku nejde přečíst – chybí oprávnění (řeší „Opravit práva ve složce“)."""


def _errmsg(exc):
    """Text výjimky; záměrné přeskočení (Skip) zůstane rozpoznatelné."""
    if exc.args and isinstance(exc.args[0], Skip):
        return exc.args[0]
    return str(exc)


_XLIB = None
_XATTR_NOFOLLOW = 0x1
_ACL_TYPE_EXTENDED = 0x100


def _xl():
    """libSystem s funkcemi pro rozšířené atributy a ACL (macOS)."""
    global _XLIB
    if _XLIB is None:
        try:
            lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            cp, sz, vp = ctypes.c_char_p, ctypes.c_size_t, ctypes.c_void_p
            lib.listxattr.argtypes, lib.listxattr.restype = [cp, vp, sz, ctypes.c_int], ctypes.c_ssize_t
            lib.getxattr.argtypes = [cp, cp, vp, sz, ctypes.c_uint32, ctypes.c_int]
            lib.getxattr.restype = ctypes.c_ssize_t
            lib.setxattr.argtypes = [cp, cp, vp, sz, ctypes.c_uint32, ctypes.c_int]
            lib.setxattr.restype = ctypes.c_int
            lib.removexattr.argtypes, lib.removexattr.restype = [cp, cp, ctypes.c_int], ctypes.c_int
        except (OSError, AttributeError) as exc:
            # bez těchto funkcí nejde metadata ověřit ani zachovat → akce, které je potřebují, se přeskočí
            raise OSError(T("systémové funkce pro metadata nejsou dostupné ({0})", exc))
        try:
            lib.acl_get_link_np.argtypes, lib.acl_get_link_np.restype = [cp, ctypes.c_int], vp
            lib.acl_set_link_np.argtypes, lib.acl_set_link_np.restype = [cp, ctypes.c_int, vp], ctypes.c_int
            lib.acl_init.argtypes, lib.acl_init.restype = [ctypes.c_int], vp
            lib.acl_free.argtypes, lib.acl_free.restype = [vp], ctypes.c_int
            lib.has_acl = True
        except AttributeError:
            lib.has_acl = False
        _XLIB = lib
    return _XLIB


def xattr_list(path):
    if not IS_MAC:
        return []
    lib, p = _xl(), os.fsencode(path)
    n = lib.listxattr(p, None, 0, _XATTR_NOFOLLOW)
    if n <= 0:
        return []
    buf = ctypes.create_string_buffer(n)
    n = lib.listxattr(p, buf, n, _XATTR_NOFOLLOW)
    return [x.decode("utf-8", "surrogateescape") for x in buf.raw[:max(n, 0)].split(b"\0") if x]


def _xattr(path, name):
    """Hodnota rozšířeného atributu (bytes), nebo None."""
    if not IS_MAC:
        return None
    lib, p, nm = _xl(), os.fsencode(path), name.encode("utf-8", "surrogateescape")
    n = lib.getxattr(p, nm, None, 0, 0, _XATTR_NOFOLLOW)
    if n < 0:
        return None
    buf = ctypes.create_string_buffer(max(n, 1))
    n = lib.getxattr(p, nm, buf, n, 0, _XATTR_NOFOLLOW)
    return buf.raw[:n] if n >= 0 else None


def xattr_set(path, name, value):
    return IS_MAC and _xl().setxattr(os.fsencode(path), name.encode("utf-8", "surrogateescape"),
                                     value, len(value), 0, _XATTR_NOFOLLOW) == 0


def xattr_del(path, name):
    return IS_MAC and _xl().removexattr(os.fsencode(path), name.encode("utf-8", "surrogateescape"),
                                        _XATTR_NOFOLLOW) == 0


def copy_acl(src, dst):
    """Nastaví `dst` stejný seznam ACL jako má `src` (nebo žádný). True = hotovo, False = selhalo,
    None = nejde zjistit."""
    if not IS_MAC:
        return True
    lib = _xl()
    if not lib.has_acl:
        return None                            # nejde zjistit (funkce chybí) – jen zapsat do záznamu
    acl = lib.acl_get_link_np(os.fsencode(src), _ACL_TYPE_EXTENDED)
    if not acl:
        acl = lib.acl_init(0)                  # src nemá ACL → dst také žádné
    if not acl:
        return False
    try:
        return lib.acl_set_link_np(os.fsencode(dst), _ACL_TYPE_EXTENDED, acl) == 0
    finally:
        lib.acl_free(acl)


def user_meta_same(a, b):
    """Štítky Finderu a komentář shodné? (důležité u trvalé náhrady klonem / pevným odkazem)"""
    return all(_xattr(a, n) == _xattr(b, n) for n in USER_META_XATTRS)


def same_physical(a, b):
    """Je to tentýž soubor? (stejný inode, nebo stejný síťový disk připojený dvakrát)"""
    sa, sb = os.stat(a), os.stat(b)
    if (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino):
        return True
    if IS_MAC and (is_network(a) or is_network(b)):
        mark = uuid.uuid4().hex.encode()
        name = "cz.duplicitni.kontrola"
        # značka se zapíše na DUPLIKÁT (b) – ponechaný originál se nikdy nemění
        if not xattr_set(b, name, mark):
            return True                         # nejde ověřit → raději považovat za tentýž
        try:
            return _xattr(a, name) == mark
        finally:
            xattr_del(b, name)
    return False


def check_pair(keeper, dup, strict_meta=False, own_rsrc_ok=False, replace=False):
    """Smí se `dup` odstranit, když zůstane `keeper`? Vrací None (ano) nebo důvod, proč ne."""
    try:
        sk = os.stat(keeper.path)
    except OSError:
        return Skip(T("ponechaný soubor už neexistuje nebo není dostupný"))
    try:
        sd = os.lstat(dup.path)
    except OSError:
        return Skip(T("soubor už neexistuje"))
    if not stat.S_ISREG(sk.st_mode) or not stat.S_ISREG(sd.st_mode):
        return Skip(T("není to obyčejný soubor"))
    if sk.st_size != keeper.size or sk.st_mtime != keeper.mtime:
        return Skip(T("ponechaný soubor se od hledání změnil – hledej znovu"))
    if sd.st_size != dup.size or sd.st_mtime != dup.mtime:
        return Skip(T("soubor se od hledání změnil – hledej znovu"))
    if in_package(dup):
        return Skip(T("je uvnitř balíčku nebo skryté složky – mazat se nesmí"))
    if replace and (is_cloud(dup.path) or is_cloud(keeper.path)):
        return Skip(T("je ve složce synchronizované s cloudem (OneDrive, Google Drive, iCloud…) – náhrada by "
                      "soubor znovu nahrála do cloudu a mohla smazat jeho historii verzí a sdílení; přeskočeno "
                      "(použij Do Koše)"))
    if (getattr(sk, "st_flags", 0) | getattr(sd, "st_flags", 0)) & SF_DATALESS:
        return Skip(T("soubor je jen v cloudu (není stažený) – ověření shody by ho celý stáhlo; přeskočeno "
                      "(stáhni ho ve Finderu: pravé tlačítko → Stáhnout nyní)"))
    try:
        if same_physical(keeper.path, dup.path):
            return Skip(T("je to tentýž soubor (stejný disk připojený dvakrát?) – přeskočeno"))
        filecmp.clear_cache()
        if not filecmp.cmp(keeper.path, dup.path, shallow=False):
            return Skip(T("obsah se liší od ponechaného souboru (jeden z nich může být poškozený) – přeskočeno"))
        if not own_rsrc_ok and not rsrc_same(keeper.path, dup.path):
            return Skip(T("liší se resource fork (náhled/ikona starších Mac souborů) – přeskočeno (APFS klon si ho umí ponechat)"))
    except PermissionError as exc:             # oprávnění / Plný přístup k disku → normální rozbor
        return PermMsg(T("soubor nejde přečíst – chybí oprávnění: {0}", exc.strerror or exc))
    except OSError as exc:
        return Skip(T("soubor nejde celý přečíst (může být poškozený): {0} – přeskočeno", exc.strerror or exc))
    if strict_meta and not user_meta_same(keeper.path, dup.path):
        return Skip(T("má jiné štítky nebo komentář Finderu – přeskočeno (pevný odkaz by je přepsal; použij APFS klon)"))
    return None


def precheck(items, strict_meta=False, cancel=None, progress=None, own_rsrc_ok=False, replace=False):
    """items = [(seznam ponechaných, soubor k odstranění)].
    Vrací ([(ověřený ponechaný, soubor)], [(cesta, důvod)])."""
    ok, err = [], []
    total = sum(f.size for _, f in items) or 1
    done = 0
    for i, (keepers, f) in enumerate(items, 1):
        if cancel is not None and cancel.is_set():
            break
        if progress:
            progress(T("Ověřuji shodu s originálem {0}/{1}: {2}", i, len(items), f.name), done / total, f.path)
        reason = Skip(T("chybí ponechaný soubor"))
        for k in keepers:
            reason = check_pair(k, f, strict_meta, own_rsrc_ok, replace)
            if reason is None:
                ok.append((k, f))
                break
        if reason is not None:
            err.append((f.path, reason))
        done += f.size
    return ok, err


# ---------------- celé duplicitní složky ----------------

class DirInfo:
    """Složka v pohledu „Složky“ – chová se pro označování jako soubor (path, root, size, mtime, btime)."""
    __slots__ = ("path", "root", "name", "files", "size", "mtime", "btime", "marked", "clone", "locked")

    def __init__(self, path, root, files):
        self.path, self.root, self.files = path, root, files      # files: {normalizovaná rel. cesta: FileInfo}
        self.name = os.path.basename(path) or path
        fl = list(files.values())
        self.size = sum(f.size for f in fl)
        self.mtime = max((f.mtime for f in fl), default=0)
        self.btime = min((f.btime for f in fl), default=0)
        self.marked, self.clone, self.locked = False, None, False


class FolderGroup:
    def __init__(self, dirs, verified):
        self.files = dirs            # jménem „files“ kvůli společnému označování se skupinami souborů
        self.verified = verified
        self.merged = False

    @property
    def name(self):
        return self.files[0].name if self.files else ""

    @property
    def total(self):
        return sum(d.size for d in self.files)

    @property
    def wasted(self):
        return self.total - max(d.size for d in self.files) if self.files else 0

    @property
    def nfiles(self):
        return len(self.files[0].files) if self.files else 0


def find_dup_folders(all_files, groups, cancel=None):
    """Najde složky, jejichž VŠECHNY (prohledané) soubory mají ve druhé složce kopii na stejném
    relativním místě. Vrací jen „nejvyšší“ takové složky (ne každou podsložku zvlášť)."""
    gid = {}
    for i, g in enumerate(groups):
        for f in g.files:
            gid[id(f)] = i
    mask = (1 << 64) - 1
    tot, acc, roots = {}, {}, {}
    for n, f in enumerate(all_files):
        if cancel is not None and n % 20000 == 0 and cancel.is_set():
            raise Cancelled()
        d = os.path.dirname(f.path)
        g = gid.get(id(f))
        while True:
            tot[d] = tot.get(d, 0) + 1
            if g is not None:
                h = hash((norm_name(f.path[len(d) + 1:]), g)) & mask
                a = acc.get(d)
                if a is None:
                    acc[d] = [1, h, f.size]
                    roots[d] = f.root
                else:
                    a[0] += 1
                    a[1] = (a[1] + h) & mask
                    a[2] += f.size
            if len(d) <= len(f.root.rstrip("/")) or d == "/":
                break
            d = os.path.dirname(d)
    buckets = {}
    for d, (cnt, h, size) in acc.items():
        if cnt == tot.get(d) and size > 0:
            buckets.setdefault((cnt, h, size), []).append(d)
    # přesné ověření kandidátů (hash součtu může kolidovat)
    cand_dirs = {d for b in buckets.values() if len(b) > 1 for d in b}
    members = {d: {} for d in cand_dirs}
    if cand_dirs:
        for g in groups:
            for f in g.files:
                d = os.path.dirname(f.path)
                while True:
                    if d in members:
                        members[d][norm_name(f.path[len(d) + 1:])] = f
                    if len(d) <= len(f.root.rstrip("/")) or d == "/":
                        break
                    d = os.path.dirname(d)
    result = []
    for b in buckets.values():
        if len(b) < 2:
            continue
        exact = {}
        for d in b:
            key = frozenset((rel, gid[id(f)]) for rel, f in members[d].items())
            exact.setdefault(key, []).append(d)
        for ds in exact.values():
            ds = [d for d in ds if not any(o != d and in_folder(d, o) for o in ds)]   # bez vnořených
            if len(ds) > 1:
                dirs = [DirInfo(d, roots[d], members[d]) for d in sorted(ds)]
                result.append(FolderGroup(dirs, all(groups[gid[id(f)]].verified
                                                    for f in members[ds[0]].values())))
    # jen nejvyšší úroveň: skupinu vynechat, když všechny její složky leží ve složkách jiné skupiny
    sets = {frozenset(norm_name(d.path) for d in fg.files) for fg in result}
    out = []
    for fg in result:
        parents = frozenset(norm_name(os.path.dirname(d.path)) for d in fg.files)
        if len(parents) == len(fg.files) and parents in sets:
            continue
        out.append(fg)
    out.sort(key=lambda fg: -fg.wasted)
    return out


def _raise(exc):
    raise exc


def _tree_files(root):
    """ÚPLNĚ všechny soubory a odkazy ve složce – i skryté, systémové ($RECYCLE.BIN, .Trashes…)
    a „._“ soubory, protože do Koše jde celá složka. Vynechá se jen .DS_Store (nastavení zobrazení).
    Nečitelná podsložka vyvolá chybu → složka se přeskočí. {norm. rel: (cesta, druh)}"""
    out = {}
    for dp, dn, fn in os.walk(root, onerror=_raise):
        for n in fn + [d for d in dn if os.path.islink(os.path.join(dp, d))]:
            if n == ".DS_Store":
                continue
            p = os.path.join(dp, n)
            out[norm_name(os.path.relpath(p, root))] = (p, "l" if os.path.islink(p) else "f")
    return out


def check_folder_pair(keep, dup):
    """Smí jít složka `dup` celá do Koše, když zůstane `keep`? None = ano, jinak důvod.
    Obě složky se projdou ZNOVU (i skryté a malé soubory) a každý soubor se porovná bajt po bajtu."""
    if not os.path.isdir(keep.path):
        return Skip(T("ponechaná složka už neexistuje"))
    if not os.path.isdir(dup.path) or os.path.islink(dup.path):
        return Skip(T("složka už neexistuje"))
    if paths_overlap(keep.path, dup.path):
        return Skip(T("složky jsou jedna v druhé – přeskočeno"))
    if in_package(dup):
        return Skip(T("složka je uvnitř balíčku nebo skryté složky – mazat se nesmí"))
    try:
        a, b = _tree_files(keep.path), _tree_files(dup.path)
        if set(a) != set(b):
            extra = sorted(set(b) - set(a))[:3] or sorted(set(a) - set(b))[:3]
            return Skip(T("složka neobsahuje přesně tytéž soubory jako ponechaná (např. ")
                        + ", ".join(extra) + T(") – přeskočeno"))
        first = True
        for rel, (pb, kb) in b.items():
            pa, ka = a[rel]
            if ka != kb:
                return Skip(T("„{0}“ je v jedné složce odkaz a ve druhé soubor – přeskočeno", rel))
            if kb == "l":
                if os.readlink(pa) != os.readlink(pb):
                    return Skip(T("odkaz „{0}“ míří jinam – přeskočeno", rel))
                continue
            if is_dataless(pa) or is_dataless(pb):
                return Skip(T("soubor „{0}“ je jen v cloudu (není stažený) – ověření by ho celý stáhlo; přeskočeno", rel))
            if first:
                first = False
                if same_physical(pa, pb):
                    return Skip(T("je to tatáž složka (stejný disk připojený dvakrát?) – přeskočeno"))
            if not same_content(pa, pb):
                return Skip(T("soubor „{0}“ se liší od ponechaného – přeskočeno", rel))
            if not rsrc_same(pa, pb):
                return Skip(T("soubor „{0}“ má jiný resource fork – přeskočeno", rel))
    except PermissionError as exc:
        return PermMsg(T("složku nejde přečíst – chybí oprávnění: {0}", exc.strerror or exc))
    except OSError as exc:
        return Skip(T("složku nejde celou přečíst (může být poškozená): {0} – přeskočeno", exc.strerror or exc))
    return None


def staging_leftovers():
    """Pomocné složky po přerušeném mazání s heslem správce, ve kterých něco zůstalo."""
    cands = [os.path.join(SUPPORT_DIR, "Ke smazani")]
    try:
        cands += [os.path.join("/Volumes", v, ".DuplicitniSoubory-ke-smazani") for v in os.listdir("/Volumes")]
    except OSError:
        pass
    out = []
    for c in cands:
        try:
            if any(os.scandir(c)):
                out.append(c)
        except OSError:
            pass
    return out


def _tmp_beside(path):
    return os.path.join(os.path.dirname(path), f".dup-tmp-{uuid.uuid4().hex[:8]}")


def same_content(a, b):
    filecmp.clear_cache()
    return os.path.getsize(a) == os.path.getsize(b) and filecmp.cmp(a, b, shallow=False)


def _xattr_names(path):
    return xattr_list(path)


def copy_rsrc(src, dst):
    """Nastaví `dst` stejný resource fork jako má `src` (nebo žádný)."""
    if not IS_MAC or rsrc_same(src, dst):
        return
    try:
        size = os.path.getsize(_rsrc(src))
    except OSError:
        size = 0
    if size:
        with open(_rsrc(src), "rb") as fi, open(_rsrc(dst), "wb") as fo:
            shutil.copyfileobj(fi, fo)
    else:
        xattr_del(dst, "com.apple.ResourceFork")


def copy_metadata(src, dst):
    """Přenese VŠECHNA rozšířená metadata (štítky, komentář, barvu, původ…) ze `src` na `dst`
    a odstraní ta, která `src` nemá. Data souboru se nemění. Vrací True, když štítky a komentář sedí."""
    if not IS_MAC:
        return True
    want = _xattr_names(src)
    for n in _xattr_names(dst):
        if n not in want and n != "com.apple.ResourceFork":
            xattr_del(dst, n)
    for n in want:
        if n == "com.apple.ResourceFork":       # resource fork řeší copy_rsrc()
            continue
        v = _xattr(src, n)
        if v is not None and _xattr(dst, n) != v:
            xattr_set(dst, n, v)                # chráněné systémové atributy zápis odmítnou – nevadí
    return user_meta_same(src, dst)


def replace_with_clone(keeper, dup):
    """APFS klon: soubor zůstane na svém místě i se jménem a datem změny, ale data sdílí
    s originálem → místo se uvolní. Úprava jednoho souboru druhý neovlivní."""
    if os.stat(keeper).st_dev != os.stat(dup).st_dev:
        raise OSError(Skip(T("soubory jsou na různých discích – klon není možný, přeskočeno")))
    if IS_MAC and fs_type(dup) != "apfs":
        raise OSError(Skip(T("disk není APFS ({0}) – klon není možný, přeskočeno", fs_type(dup) or T("neznámý typ"))))
    st = os.lstat(dup)
    tmp = _tmp_beside(dup)
    r = subprocess.run(["/bin/cp", "-c", keeper, tmp], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(tmp):
        _remove_tmp(tmp)
        raise OSError(Skip((r.stderr or T("klonování selhalo")).strip() + T(" – přeskočeno")))
    try:
        # cp -c převezme příznaky (zámek, skrytí…) i ACL ponechaného souboru → zrušit, nastaví se vlastní
        tfl = getattr(os.lstat(tmp), "st_flags", 0)
        if tfl & ~UF_COMPRESSED and hasattr(os, "chflags"):
            os.chflags(tmp, tfl & UF_COMPRESSED)
        if not same_content(tmp, dup):
            raise OSError(Skip(T("klon se neshoduje s nahrazovaným souborem – nic se nezměnilo")))
        # klon sdílí jen data; resource fork, štítky, komentář a ostatní metadata si soubor ponechá svoje
        copy_rsrc(dup, tmp)
        if not copy_metadata(dup, tmp):
            raise OSError(Skip(T("štítky nebo komentář Finderu se nepodařilo zachovat – soubor přeskočen")))
        if not rsrc_same(tmp, dup):
            raise OSError(Skip(T("resource fork se nepodařilo zachovat – soubor přeskočen, nic se nezměnilo")))
        acl_ok = copy_acl(dup, tmp)
        if acl_ok is False:
            raise OSError(Skip(T("oprávnění (ACL) se nepodařilo zachovat – přeskočeno, nic se nezměnilo")))
        os.chmod(tmp, stat.S_IMODE(st.st_mode))
        os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns))
        os.replace(tmp, dup)
    except OSError:
        _remove_tmp(tmp)
        raise
    # příznaky nahrazovaného souboru (skrytí, štítek…; zámek až po přejmenování), komprese podle klonu
    if hasattr(os, "chflags"):
        cur = getattr(os.lstat(dup), "st_flags", 0)
        want = (st.st_flags & 0xFFFF & ~UF_COMPRESSED) | (cur & UF_COMPRESSED)
        for flags in (want, want & (0x8000 | 0x20 | 0x1 | 0x2 | 0x4 | 0x8)):  # vše / jen běžné (skryté, zámek…)
            try:
                os.chflags(dup, flags)
                break
            except OSError:
                continue
    ck = clone_id(keeper)
    _log("KLON", dup, keeper, (T("sdílí data") if ck and ck == clone_id(dup) else T("klon nerozpoznán"))
         + ("" if acl_ok else T("; ACL nešlo ověřit")))


UF_COMPRESSED = getattr(stat, "UF_COMPRESSED", 0x20)


def _remove_tmp(tmp):
    """Smaže JEN vlastní dočasný soubor .dup-tmp-… (i když převzal zámek)."""
    if not os.path.basename(tmp).startswith(".dup-tmp-") or not os.path.lexists(tmp):
        return
    try:
        if hasattr(os, "lchflags"):
            os.lchflags(tmp, 0)
    except OSError:
        pass
    try:
        os.remove(tmp)
    except OSError as exc:
        _log("ZBYL_DOCASNY", tmp, "", T("nepodařilo se smazat dočasný soubor: {0}", exc))


def replace_with_hardlink(keeper, dup):
    if os.stat(keeper).st_dev != os.stat(dup).st_dev:
        raise OSError(T("soubory jsou na různých discích"))
    tmp = _tmp_beside(dup)
    os.link(keeper, tmp)
    try:
        if not (same_content(tmp, dup) and rsrc_same(tmp, dup)):
            raise OSError(Skip(T("ponechaný soubor se mezitím změnil – nic se nezměnilo")))
        os.replace(tmp, dup)
    except OSError:
        os.remove(tmp)
        raise
    _log("PEVNY_ODKAZ", dup, keeper)


def _link_then_trash(keeper, dup, make_link, visible_tmp=False):
    """Vytvoří odkaz pod dočasným jménem, originál dá do Koše a odkaz přejmenuje.
    Když cokoli selže, soubor zůstane na místě."""
    base = os.path.join(os.path.dirname(dup), T("{0} (dočasný odkaz {1})", os.path.basename(dup), uuid.uuid4().hex[:6])) \
        if visible_tmp else _tmp_beside(dup)
    tmp = base
    make_link(tmp)
    if not os.path.lexists(tmp):
        raise OSError(Skip(T("odkaz se nepodařilo vytvořit – soubor zůstal na místě")))
    try:                                        # ponechaný musí pořád existovat a být shodný
        same = same_content(keeper, dup)
    except OSError:
        same = False
    if not same:
        os.remove(tmp)
        raise OSError(Skip(T("ponechaný soubor se mezitím změnil nebo zmizel – soubor zůstal na místě")))
    ok, err = trash_paths([dup])
    if err:
        os.remove(tmp)
        msg = err[0][1] + T(" – soubor zůstal na místě")
        raise OSError(Skip(msg) if isinstance(err[0][1], Skip) else msg)
    try:
        os.rename(tmp, dup)
    except OSError as exc:
        raise OSError(T("původní soubor je v Koši, odkaz se ale jmenuje „{0}“ ({1})", os.path.basename(tmp), exc))


def replace_with_symlink(keeper, dup):
    _link_then_trash(keeper, dup, lambda tmp: os.symlink(keeper, tmp))
    _log("SYMLINK", dup, keeper, T("původní v Koši"))


def replace_with_alias(keeper, dup):
    if not IS_MAC:
        raise OSError(T("alias Finderu jde vytvořit jen na macOS"))

    def make(tmp):
        r = subprocess.run(["/usr/bin/osascript", "-e", _ALIAS_SCRIPT, keeper,
                            os.path.dirname(tmp), os.path.basename(tmp)], capture_output=True, text=True)
        if r.returncode != 0:
            raise OSError(Skip(T("alias se nepodařilo vytvořit – originál zůstal na místě: ") + r.stderr.strip()))
    _link_then_trash(keeper, dup, make, visible_tmp=True)
    _log("ALIAS", dup, keeper, T("původní v Koši"))


def _unique(path):
    if not os.path.lexists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 2
    while os.path.lexists(f"{base} ({i}){ext}"):
        i += 1
    return f"{base} ({i}){ext}"


def move_to_folder(f, dest_root):
    """Přesune soubor do cílové složky se zachováním struktury podsložek."""
    rel = os.path.relpath(f.path, f.root)
    root_name = os.path.basename(f.root.rstrip("/")) or "Disk"
    target = _unique(os.path.join(dest_root, root_name, rel))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if os.stat(f.path).st_dev == os.stat(os.path.dirname(target)).st_dev:
        linked = False
        try:                                   # pevný odkaz + odpojení = přesun, který nikdy nic nepřepíše
            os.link(f.path, target)
            linked = True
        except FileExistsError:
            raise OSError(T("cíl už existuje: {0}", target))
        except OSError:                        # disk bez pevných odkazů (exFAT…)
            if os.path.lexists(target):
                raise OSError(T("cíl už existuje: {0}", target))
            os.rename(f.path, target)
        if linked:
            try:
                os.unlink(f.path)
            except OSError:
                os.unlink(target)              # zrušit jen nový odkaz, originál zůstává
                raise
    else:                                      # jiný disk: zkopírovat i s metadaty, ověřit, originál do Koše
        copy_item(f.path, target)
        if not (same_content(f.path, target) and rsrc_same(f.path, target)):
            raise OSError(Skip(T("kopie v „{0}“ se neshoduje s originálem – originál zůstal na místě", target)))
        ok, err = trash_paths([f.path])
        if err:
            _log("KOPIE", f.path, target, T("originál nešel do Koše"))
            raise OSError(Skip(T("zkopírováno do „{0}“, originál ale zůstal na místě ({1})", target, err[0][1])))
    _log("PRESUN", f.path, target)
    return target


REPLACE_ACTIONS = {
    "clone": (T("APFS klonem"), replace_with_clone, True),
    "hardlink": (T("pevným odkazem"), replace_with_hardlink, True),
    "alias": (T("aliasem Finderu"), replace_with_alias, False),
    "symlink": (T("symbolickým odkazem"), replace_with_symlink, False),
}


def run_replace(pairs, kind, cancel=None, progress=None):
    """Nahradí soubory odkazem/klonem. pairs = [(ponechaný, soubor)] – vždy nejdřív
    prošlé funkcí precheck() (bajtová shoda s čitelným originálem)."""
    label, fn, _ = REPLACE_ACTIONS[kind]
    done, errors = [], []
    total = len(pairs) or 1
    for i, (keeper, f) in enumerate(pairs, 1):
        if cancel is not None and cancel.is_set():
            break
        if progress:
            progress(T("Nahrazuji {0}… {1}/{2}", label, i, total), i / total, f.path)
        try:
            fn(keeper.path, f.path)
            done.append(f)
        except OSError as exc:
            errors.append((f.path, _errmsg(exc)))
    return done, errors


def export_csv(groups, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow([T("Skupina"), T("Obsah ověřen"), T("Označeno"), T("Název"), T("Velikost (B)"),
                    T("Změněno"), T("Vytvořeno"), T("Cesta")])
        for i, g in enumerate(groups, 1):
            for f in g.files:
                w.writerow([i, T("ano") if g.verified else T("ne"), T("ano") if f.marked else "",
                            f.name, f.size, fmt_date(f.mtime), fmt_date(f.btime), f.path])


def fmt_size(n):
    n = float(n)
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}".replace(".", ",")
        n /= 1000.0


def fmt_int(n):
    return f"{n:,}".replace(",", "\u00a0")


def fmt_date(ts):
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
    except (OverflowError, OSError, ValueError):
        return "?"


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        os.makedirs(SUPPORT_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass


# ======================================================================================
#  POROVNÁNÍ DVOU MÍST + DOPLNĚNÍ (logika bez GUI)
#  Zásada: nic se nemaže ani nepřepisuje. Chybějící soubory se jen kopírují;
#  u rozdílných verzí se starší jen PŘEJMENUJE a uchová na obou stranách.
# ======================================================================================

MTIME_TOLERANCE = 2.0            # FAT/exFAT ukládá čas s přesností 2 s

MATCH_MODES = {                  # jak poznat „stejný soubor“
    "quick": T("velikost + datum změny"),
    "size": T("jen velikost"),
    "content": T("obsah (pomalé, jisté)"),
}
LAYOUT_MODES = {                 # kde soubor hledat na druhé straně
    "path": T("na stejném místě (stejná struktura složek)"),
    "anywhere": T("kdekoli (jinak uspořádané složky)"),
}
DIRECTIONS = {
    "both": T("Oboustranně  A ⇄ B  (obě místa budou mít stejný obsah)"),
    "AtoB": T("Jen doplnit B  (A → B)"),
    "BtoA": T("Jen doplnit A  (B → A)"),
}
CONFLICT_POLICIES = {
    "skip": T("Rozdílné verze přeskočit"),
    "newer": T("Novější verze vyhraje, starší se uchová jako „… (starší verze …)“"),
}


class Entry:
    __slots__ = ("rel", "key", "kind", "size", "mtime", "path", "count")

    def __init__(self, rel, kind, size, mtime, path):
        self.rel, self.kind, self.size, self.mtime, self.path = rel, kind, size, mtime, path
        self.key = norm_name(rel)
        self.count = 1


class CompareItem:
    """status: onlyA, onlyB, same, diff, type"""
    __slots__ = ("status", "a", "b", "include", "note")

    def __init__(self, status, a=None, b=None, note=""):
        self.status, self.a, self.b, self.note = status, a, b, note
        self.include = status in ("onlyA", "onlyB")

    @property
    def rel(self):
        return (self.a or self.b).rel


def scan_tree(root, hidden=True, cancel=None, progress=None, label=""):
    """Projde celý strom včetně balíčků (.app…) – pro kopírování musí být úplný.
    Vrací {klíč: Entry} se soubory ('f'), složkami ('d') a symbolickými odkazy ('l')."""
    root = os.path.abspath(root)
    entries, errors = {}, 0
    root_skip = SYSTEM_ROOT_SKIP if root == "/" else set()
    stack, last, nfiles = [root], 0.0, 0
    while stack:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            errors += 1
            continue
        with it:
            for e in it:
                name = e.name
                if name in SKIP_FILE_NAMES or name in SKIP_DIR_NAMES or name.startswith("._"):
                    continue
                if not hidden and name.startswith("."):
                    continue
                if e.path in root_skip or name.startswith(".dup-tmp-"):
                    continue
                rel = os.path.relpath(e.path, root)
                try:
                    if e.is_symlink():
                        _put(entries, Entry(rel, "l", 0, 0, e.path))
                    elif e.is_dir(follow_symlinks=False):
                        _put(entries, Entry(rel, "d", 0, 0, e.path))
                        stack.append(e.path)
                    elif e.is_file(follow_symlinks=False):
                        st = e.stat(follow_symlinks=False)
                        _put(entries, Entry(rel, "f", st.st_size, st.st_mtime, e.path))
                        nfiles += 1
                except OSError:
                    errors += 1
        if progress is not None:
            now = time.monotonic()
            if now - last > 0.15:
                last = now
                progress(T("Procházím {0}… {1} souborů", label, fmt_int(nfiles)), None, d)
    return entries, errors


def _put(entries, e):
    """Uloží položku. Dva názvy lišící se jen velikostí písmen (Foo.txt × foo.txt na disku,
    který je rozlišuje) se nesmí slít do jednoho – druhý dostane vlastní klíč a ukáže se zvlášť."""
    if e.key in entries and entries[e.key].rel != e.rel:
        e.key = e.key + "\x00" + e.rel
    entries[e.key] = e


def _parent(key):
    return key.rpartition("/")[0]


def _fill_dir_totals(item_entry, side_entries, sorted_keys):
    """Pro chybějící složku spočítá počet souborů a velikost celého obsahu."""
    import bisect
    prefix = item_entry.key + "/"
    i = bisect.bisect_left(sorted_keys, prefix)
    count = size = 0
    while i < len(sorted_keys) and sorted_keys[i].startswith(prefix):
        e = side_entries[sorted_keys[i]]
        if e.kind == "f":
            count += 1
            size += e.size
        i += 1
    item_entry.count, item_entry.size = count, size


def _same_file(a, b, match):
    if a.size != b.size:
        return False, T("jiná velikost")
    if match == "quick" and abs(a.mtime - b.mtime) > MTIME_TOLERANCE:
        return False, T("jiné datum změny")
    return True, ""


def compare_trees(A, B, layout="path", match="quick", cancel=None, progress=None):
    """Porovná dva výsledky scan_tree. Vrací seznam CompareItem."""
    items = []
    if layout == "path":
        keysA, keysB = set(A), set(B)
        for src, other, status in ((A, B, "onlyA"), (B, A, "onlyB")):
            sk = sorted(src)
            for k in sk:
                if k in other:
                    continue
                par = _parent(k)
                # pokryto chybějící nadřazenou složkou (nebo na druhé straně je na jejím místě soubor)
                if par and (par not in other or other[par].kind != "d"):
                    continue
                e = src[k]
                if e.kind == "d":
                    _fill_dir_totals(e, src, sk)
                items.append(CompareItem(status, a=e if status == "onlyA" else None,
                                         b=e if status == "onlyB" else None))
        to_hash = []
        for k in sorted(keysA & keysB):
            a, b = A[k], B[k]
            if a.kind == "d" and b.kind == "d":
                continue
            if a.kind != b.kind:
                items.append(CompareItem("type", a, b, T("na jedné straně složka/odkaz, na druhé soubor")))
            elif a.kind == "l":
                try:
                    same = os.readlink(a.path) == os.readlink(b.path)
                except OSError:
                    same = False
                items.append(CompareItem("same" if same else "diff", a, b, "" if same else T("jiný cíl odkazu")))
            else:
                same, note = _same_file(a, b, match)
                if same and match == "content":
                    to_hash.append((a, b))
                else:
                    items.append(CompareItem("same" if same else "diff", a, b, note))
        if to_hash:
            total = sum(a.size for a, _ in to_hash) or 1
            done = 0
            for i, (a, b) in enumerate(to_hash, 1):
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                if progress:
                    progress(T("Porovnávám obsah… {0}/{1}", i, len(to_hash)), done / total, a.path)
                try:
                    filecmp.clear_cache()
                    same = filecmp.cmp(a.path, b.path, shallow=False)
                    note = "" if same else T("jiný obsah")
                except OSError as exc:
                    same, note = False, T("nelze přečíst: {0}", exc)
                done += a.size
                items.append(CompareItem("same" if same else "diff", a, b, note))
    else:   # kdekoli – podle názvu+velikosti, velikosti, nebo obsahu
        fa = [e for e in A.values() if e.kind == "f"]
        fb = [e for e in B.values() if e.kind == "f"]
        if match == "content":
            common = {e.size for e in fa} & {e.size for e in fb}
            cand = [e for e in fa + fb if e.size in common]
            total = sum(e.size for e in cand) or 1
            done = [0]
            digests = {}
            for i, e in enumerate(cand, 1):
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                if progress and i % 20 == 1:
                    progress(T("Počítám otisky obsahu… {0}/{1}", i, len(cand)), done[0] / total, e.path)
                try:
                    digests[id(e)] = file_digest(e.path, cancel=cancel)
                except OSError:
                    pass
                done[0] += e.size

            def keyfn(e):
                return (e.size, digests.get(id(e), ("chyba", id(e))))
        elif match == "size":
            def keyfn(e):
                return (e.size,)
        else:   # název + velikost + datum změny (zaokrouhleno na 2 s kvůli FAT/exFAT)
            def keyfn(e):
                return (norm_name(os.path.basename(e.rel)), e.size, int(e.mtime // 2))
        # párovat 1:1 – dva různé soubory v A se nesmí „schovat“ za jeden soubor v B
        ma, mb = {}, {}
        for e in fa:
            ma.setdefault(keyfn(e), []).append(e)
        for e in fb:
            mb.setdefault(keyfn(e), []).append(e)
        for k, la in ma.items():
            lb = mb.get(k, [])
            for i, e in enumerate(la):
                items.append(CompareItem("same", e, lb[i]) if i < len(lb) else CompareItem("onlyA", a=e))
        for k, lb in mb.items():
            for e in lb[len(ma.get(k, [])):]:
                items.append(CompareItem("onlyB", b=e))
    order = {"onlyA": 0, "onlyB": 1, "diff": 2, "type": 3, "same": 4}
    items.sort(key=lambda it: (order[it.status], it.rel.casefold()))
    return items


def copy_item(src, dst):
    """Zkopíruje soubor / celou složku / symbolický odkaz i s metadaty (ditto).
    NIKDY nepřepíše existující cíl – kopíruje do dočasného jména a pak přejmenuje."""
    if os.path.lexists(dst):
        raise FileExistsError(T("cíl už existuje: {0}", dst))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.islink(src):
        os.symlink(os.readlink(src), dst)
        return
    tmp = _tmp_beside(dst)
    try:
        if IS_MAC:
            r = subprocess.run(["/usr/bin/ditto", src, tmp], capture_output=True, text=True)
            if r.returncode != 0:
                raise OSError(r.stderr.strip() or T("kopírování selhalo"))
        elif os.path.isdir(src):
            shutil.copytree(src, tmp, symlinks=True)
        else:
            shutil.copy2(src, tmp)
        if os.path.lexists(dst):
            raise FileExistsError(T("cíl mezitím vznikl: {0}", dst))
        os.rename(tmp, dst)
    finally:
        if os.path.lexists(tmp):          # jen vlastní nedokončená dočasná kopie
            if os.path.isdir(tmp) and not os.path.islink(tmp):
                shutil.rmtree(tmp, ignore_errors=True)
            else:
                os.remove(tmp)


def _tree_totals(path):
    if os.path.isfile(path) or os.path.islink(path):
        return 1, os.lstat(path).st_size
    n = size = 0
    for dp, dn, fn in os.walk(path):
        for f in fn:
            if f in SKIP_FILE_NAMES or f.startswith("._"):
                continue
            n += 1
            size += os.lstat(os.path.join(dp, f)).st_size
    return n, size


def verify_copy(src, dst, deep=False):
    if os.path.islink(src):
        return os.readlink(src) == os.readlink(dst)
    if os.path.isdir(src):
        return _tree_totals(src) == _tree_totals(dst)
    if os.path.getsize(src) != os.path.getsize(dst):
        return False
    if deep:
        filecmp.clear_cache()
        return filecmp.cmp(src, dst, shallow=False)
    return True


def _older_name(path, mtime):
    base, ext = os.path.splitext(path)
    if os.path.isdir(path):
        base, ext = path, ""
    d = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H.%M")
    return _unique(T("{0} (starší verze {1}){2}", base, d, ext))


def sync_plan(items, direction, policy):
    """Rozepíše položky na kroky. Vrací seznam (druh, položka, směr)."""
    steps = []
    for it in items:
        if not it.include:
            continue
        if it.status == "onlyA" and direction in ("both", "AtoB"):
            steps.append(("copy", it, "AtoB"))
        elif it.status == "onlyB" and direction in ("both", "BtoA"):
            steps.append(("copy", it, "BtoA"))
        elif it.status == "diff" and policy == "newer" and it.a.kind == "f" and it.b.kind == "f":
            if it.a.mtime == it.b.mtime:
                continue
            newer_is_a = it.a.mtime > it.b.mtime
            if direction == "AtoB" and not newer_is_a:
                continue
            if direction == "BtoA" and newer_is_a:
                continue
            steps.append(("newer", it, "AtoB" if newer_is_a else "BtoA"))
    return steps


def plan_bytes(steps):
    to_a = to_b = 0
    for kind, it, d in steps:
        if kind == "copy":
            e = it.a if d == "AtoB" else it.b
            if d == "AtoB":
                to_b += e.size
            else:
                to_a += e.size
        else:
            new, old = (it.a, it.b) if d == "AtoB" else (it.b, it.a)
            if d == "AtoB":
                to_b += new.size
                to_a += old.size
            else:
                to_a += new.size
                to_b += old.size
    return to_a, to_b


def run_sync(steps, root_a, root_b, layout="path", direction="both", verify=False,
             cancel=None, progress=None):
    """Provede kopírování. Nic nemaže ani nepřepisuje. Vrací (počet hotových, chyby)."""
    roots = {"A": root_a, "B": root_b}
    total = sum(plan_bytes(steps)) or 1
    done_bytes, done, errors = 0, 0, []
    for i, (kind, it, d) in enumerate(steps, 1):
        if cancel is not None and cancel.is_set():
            break
        src_side, dst_side = ("A", "B") if d == "AtoB" else ("B", "A")
        src = it.a if src_side == "A" else it.b
        if progress:
            progress(T("Kopíruji {0}/{1}: {2}", i, len(steps), src.rel), done_bytes / total, src.path)
        try:
            if kind == "copy":
                dst = os.path.join(roots[dst_side], src.rel)
                if layout == "anywhere":
                    dst = _unique(dst)
                copy_item(src.path, dst)
                if not verify_copy(src.path, dst, deep=verify):
                    raise OSError(T("kopie se neshoduje s originálem"))
                _log("KOPIE", src.path, dst)
                done_bytes += src.size
            else:   # novější vyhraje, starší se přejmenuje a uchová na obou stranách
                old = it.b if src_side == "A" else it.a
                old_renamed = _older_name(old.path, old.mtime)
                os.rename(old.path, old_renamed)
                _log("PREJMENOVANI", old.path, old_renamed, T("starší verze"))
                copy_item(src.path, old.path)
                if not verify_copy(src.path, old.path, deep=verify):
                    raise OSError(T("kopie se neshoduje s originálem"))
                _log("KOPIE", src.path, old.path, T("novější verze"))
                if direction == "both":
                    rel_old = os.path.relpath(old_renamed, roots[dst_side])
                    dst2 = _unique(os.path.join(roots[src_side], rel_old))
                    copy_item(old_renamed, dst2)
                    _log("KOPIE", old_renamed, dst2, T("starší verze na druhou stranu"))
                done_bytes += src.size + old.size
            done += 1
        except OSError as exc:
            hint = ""
            if isinstance(exc, PermissionError) or "not permitted" in str(exc):
                tgt = roots[dst_side]
                hint = (T(" – chybí oprávnění zapisovat do cíle nebo číst zdroj (Informace → Sdílení a oprávnění; u chráněných složek Plný přístup k disku)") if os.access(tgt, os.W_OK)
                        else T(" – do místa {0} nemáš právo zapisovat", dst_side))
            errors.append((src.path, str(exc) + hint))
    return done, errors


def export_compare_csv(items, root_a, root_b, path):
    names = {"onlyA": T("jen v A"), "onlyB": T("jen v B"), "same": T("stejné"), "diff": T("liší se"), "type": T("jiný typ")}
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow([T("Stav"), T("Poznámka"), T("Cesta v A"), T("Velikost A"), T("Změněno A"),
                    T("Cesta v B"), T("Velikost B"), T("Změněno B")])
        w.writerow(["# A = " + root_a, "", "", "", "", "# B = " + root_b])
        for it in items:
            a, b = it.a, it.b
            w.writerow([names[it.status], it.note,
                        a.rel if a else "", a.size if a else "", fmt_date(a.mtime) if a and a.kind == "f" else "",
                        b.rel if b else "", b.size if b else "", fmt_date(b.mtime) if b and b.kind == "f" else ""])


# ======================================================================================
#  GUI
# ======================================================================================

MIN_SIZES = [(T("vše (i prázdné)"), 0), (T("od 1 B"), 1), (T("od 10 kB"), 10_000), (T("od 100 kB"), 100_000),
             (T("od 1 MB"), 1_000_000), (T("od 10 MB"), 10_000_000), (T("od 100 MB"), 100_000_000)]
CHECK_ON, CHECK_OFF = "☑", "☐"


def framed_tree(parent, colors, **tree_kw):
    """Treeview s oběma posuvníky v jednom tenkém rámečku (stejně jako výpis v Katalogu souborů).
    Vrací (rámeček, strom)."""
    root = parent.winfo_toplevel()
    try:
        root.winfo_rgb("systemTextBackgroundColor")
        list_bg = "systemTextBackgroundColor"
    except tk.TclError:
        list_bg = "white"
    tf = tk.Frame(parent, bg=list_bg, bd=0, highlightthickness=0)
    tf.rowconfigure(1, weight=1)
    tf.columnconfigure(1, weight=1)
    tree = ttk.Treeview(tf, **tree_kw)
    ys = ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
    xs = ttk.Scrollbar(tf, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)

    def line(**kw):
        return tk.Frame(tf, bg=colors["border"], bd=0, highlightthickness=0, **kw)
    # horní linka jen nad posuvníkem (nad sloupci kreslí čáru záhlaví – jinak by byla dvojitá)
    line(height=1).grid(row=0, column=2, sticky="ew")
    line(width=1).grid(row=0, column=0, rowspan=4, sticky="ns")
    line(width=1).grid(row=0, column=3, rowspan=4, sticky="ns")
    line(height=1).grid(row=3, column=0, columnspan=4, sticky="ew")
    tree.grid(row=0, column=1, rowspan=2, sticky="nsew")
    ys.grid(row=1, column=2, sticky="ns")
    xs.grid(row=2, column=1, sticky="ew")
    return tf, tree


def boxed(parent, colors, padding=12):
    """Plocha s tenkou šedou linkou (místo pro přetažení složky). Vrací (rámeček, vnitřek)."""
    box = tk.Frame(parent, bg=colors["pane"], bd=0, highlightthickness=1,
                   highlightbackground=colors["border"], highlightcolor=colors["border"])
    inner = ttk.Frame(box, padding=padding)
    inner.pack(fill="both", expand=True)
    return box, inner


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.roots = []
        self.files = []              # výsledek posledního procházení (pro rychlé přeskupení)
        self.scan_sig = None
        self.groups = []             # všechny skupiny
        self.shown = []              # skupiny po filtru a seřazení
        self.iid_file = {}           # iid → FileInfo
        self.iid_group = {}          # iid → Group
        self.preview_dir = tempfile.mkdtemp(prefix="dupl-nahled-")
        self.preview_img = None
        self.preview_req = None
        s = self.settings = load_settings()
        self.sort_key = s.get("sort_key", "wasted")
        self.sort_desc = s.get("sort_desc", True)
        if self.sort_key not in ("name", "size", "mtime", "btime", "wasted"):
            self.sort_key, self.sort_desc = "wasted", True

        root.title(f"{APP_TITLE} {APP_VERSION}")
        root.geometry(s.get("geometry", "1280x800"))
        root.minsize(980, 600)

        self.v_name = tk.BooleanVar(value=s.get("name", True))
        self.v_size = tk.BooleanVar(value=s.get("size", True))
        self.v_mtime = tk.BooleanVar(value=s.get("mtime", True))
        self.v_btime = tk.BooleanVar(value=s.get("btime", False))
        self.v_content = tk.BooleanVar(value=s.get("content", False))
        self.v_hidden = tk.BooleanVar(value=s.get("hidden", False))
        self.v_packages = tk.BooleanVar(value=s.get("packages", False))
        ms = s.get("minsize")
        self.v_minsize = tk.StringVar(value=ms if ms in dict(MIN_SIZES) else MIN_SIZES[1][0])
        strat = s.get("strategy")
        self.v_strategy = tk.StringVar(value=strat if strat in STRATEGIES else list(STRATEGIES)[0])
        self.v_filter = tk.StringVar()
        self.v_hide_merged = tk.BooleanVar(value=True)
        self.v_view = tk.StringVar(value=T("Soubory"))
        self.folder_groups = []
        self.exclude = list(s.get("exclude", []))
        self.hidden_merged = 0
        self.search_cache = {}
        self.v_status = tk.StringVar(value=T("Přetáhni do okna disk nebo složku (můžeš i víc najednou)."))

        self._build_ui()
        self._bind_keys()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        if IS_MAC:
            try:   # puštění složky na ikonu v Docku
                root.createcommand("::tk::mac::OpenDocument", self.on_open_document)
            except tk.TclError:
                pass
        root.after(300, self.setup_dnd)
        root.after(100, self.poll)
        root.after(1500, self.check_leftovers)
        if self.settings.get("check_updates", True):
            root.after(3000, self.check_updates)
        root.after(24 * 3600 * 1000, self.daily_update_check)

    # ------------------------------------------------------------------ UI
    # ---------- vzhled (stejný jako Katalog souborů)
    def _palette(self):
        """Barvy: trochu ztmavená plocha uvnitř záložek a tenké šedé linky (tmavý režim zvlášť)."""
        dark = False
        try:
            dark = bool(int(self.root.tk.call("tk::unsupported::MacWindowStyle", "isdark", self.root)))
        except (tk.TclError, ValueError):
            pass
        if dark:
            def sysc(name, fallback):
                try:
                    self.root.winfo_rgb(name)
                    return name
                except tk.TclError:
                    return fallback
            return {"pane": sysc("systemWindowBackgroundColor1", "#262626"),
                    "win": sysc("systemWindowBackgroundColor", "#1e1e1e"), "border": "#4e4e4e"}
        return {"pane": "#fafafa", "win": "#ffffff", "border": "#b4b4b4"}

    def _apply_style(self):
        c = self.colors = self._palette()
        st = ttk.Style(self.root)
        for name in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TPanedwindow"):
            st.configure("Pane." + name, background=c["pane"])
        base = tkfont.nametofont("TkDefaultFont")
        self.font_big = base.copy()
        try:
            size = int(base.cget("size"))
        except (ValueError, TypeError, tk.TclError):
            size = 13
        self.font_big.configure(size=max(15, size + 2))
        self.font_title = base.copy()
        self.font_title.configure(size=13, weight="bold")
        st.configure("Big.TLabel", font=self.font_big, background=c["pane"])
        st.configure("Treeview", rowheight=22)

    def _pane_style(self, widget):
        """Widgetům uvnitř záložek nastaví ztmavené pozadí plochy (ostatní vzhled zůstává)."""
        for child in widget.winfo_children():
            cls = child.winfo_class()
            if cls in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TPanedwindow"):
                try:
                    if not str(child.cget("style")):
                        child.configure(style="Pane." + cls)
                except tk.TclError:
                    pass
            self._pane_style(child)

    def _build_pane_outline(self):
        """Ztmavená plocha záložek s tenkou linkou po okraji a zaoblenými rohy (linka vede středem záložek)."""
        c, nb = self.colors, self.nb
        self._ov = {}
        for k in ("fill", "shl", "shr"):
            self._ov[k] = tk.Frame(nb, bg=c["pane"], bd=0, highlightthickness=0)
        for k in ("tl", "tr", "l", "r", "b"):
            self._ov[k] = tk.Frame(nb, bg=c["border"], bd=0, highlightthickness=0)
        self._radius = 8
        for k in ("cTL", "cTR", "cBL", "cBR"):
            self._ov[k] = tk.Canvas(nb, width=self._radius, height=self._radius, bg=c["win"],
                                    bd=0, highlightthickness=0)
        self._draw_corners()
        self._ov_after = None
        nb.bind("<Configure>", self._schedule_outline, add="+")
        nb.bind("<<NotebookTabChanged>>", self._schedule_outline, add="+")

    def _draw_corners(self):
        c, r = self.colors, self._radius
        d = 2 * r
        for k, box, start in (("cTL", (0, 0, d, d), 90), ("cTR", (-r - 1, 0, r - 1, d), 0),
                              ("cBL", (0, -r - 1, d, r - 1), 180), ("cBR", (-r - 1, -r - 1, r - 1, r - 1), 270)):
            cv = self._ov[k]
            cv.delete("all")
            cv.create_arc(*box, start=start, extent=90, style="pieslice", fill=c["pane"], outline="")
            cv.create_arc(*box, start=start, extent=90, style="arc", outline=c["border"], width=1)

    def _schedule_outline(self, _e=None):
        if self._ov_after:
            self.root.after_cancel(self._ov_after)
        self._ov_after = self.root.after(30, self._layout_outline)

    def _tab_row(self):
        """Poloha řady záložek (x1, y1, x2, y2) – zjištěná dotazem, kde notebook má záložky."""
        nb = self.nb
        w = nb.winfo_width()

        def on_tab(x, y):
            try:
                return str(nb.index(f"@{x},{y}")) != ""
            except tk.TclError:
                return False
        hit = next(((x, y) for y in range(0, 80, 2) for x in range(0, w, 6) if on_tab(x, y)), None)
        if not hit:
            return None
        hx, hy = hit
        xs = [x for x in range(0, w, 2) if on_tab(x, hy)]
        x1, x2 = min(xs), max(xs)
        while x1 > 0 and on_tab(x1 - 1, hy):
            x1 -= 1
        while x2 < w - 1 and on_tab(x2 + 1, hy):
            x2 += 1
        y1 = hy
        while y1 > 0 and on_tab(hx, y1 - 1):
            y1 -= 1
        y2 = hy
        while y2 < 120 and on_tab(hx, y2 + 1):
            y2 += 1
        return x1, y1, x2, y2

    def _layout_outline(self):
        self._ov_after = None
        nb, ov = self.nb, self._ov
        try:
            cur = nb.nametowidget(nb.select())
        except (tk.TclError, KeyError):
            return
        W, H = nb.winfo_width(), nb.winfo_height()
        cx, cy, cw, ch = cur.winfo_x(), cur.winfo_y(), cur.winfo_width(), cur.winfo_height()
        if W < 50 or cw < 10:
            return
        tabs = self._tab_row()
        r = self._radius
        inset = max(0, min(cx // 2, cx - r - 2))
        left, right = inset, W - inset - 1
        bottom = min(H - 1, cy + ch + max(r + 1, (H - cy - ch) // 2))
        if tabs:
            tx1, ty1, tx2, ty2 = tabs
            top, tab_bottom = (ty1 + ty2) // 2, ty2 + 1
            gap = 3
            tx1, tx2 = tx1 - gap, tx2 + gap
        else:
            tx1 = tx2 = None
            top = tab_bottom = max(0, cy - inset)

        def put(k, x, y, w, h):
            if w > 0 and h > 0:
                ov[k].place(x=x, y=y, width=w, height=h)
            else:
                ov[k].place_forget()
        put("fill", left, tab_bottom, right - left + 1, bottom - tab_bottom + 1)
        if tabs:
            put("shl", left, top, tx1 - left, tab_bottom - top)
            put("shr", tx2 + 1, top, right - tx2, tab_bottom - top)
            put("tl", left + r, top, tx1 - left - r, 1)
            put("tr", tx2 + 1, top, right - tx2 - r, 1)
        else:
            put("shl", 0, 0, 0, 0)
            put("shr", 0, 0, 0, 0)
            put("tl", left + r, top, right - left + 1 - 2 * r, 1)
            put("tr", 0, 0, 0, 0)
        put("l", left, top + r, 1, bottom - top + 1 - 2 * r)
        put("r", right, top + r, 1, bottom - top + 1 - 2 * r)
        put("b", left + r, bottom, right - left + 1 - 2 * r, 1)
        put("cTL", left, top, r, r)
        put("cTR", right - r + 1, top, r, r)
        put("cBL", left, bottom - r + 1, r, r)
        put("cBR", right - r + 1, bottom - r + 1, r, r)
        for k in ("tl", "tr", "l", "r", "b", "cTL", "cTR", "cBL", "cBR", "fill", "shl", "shr"):
            self.root.tk.call("lower", ov[k]._w)

    def _build_bottom_bar(self):
        """Spodní lišta – stejná na všech záložkách: stav vlevo, jazyk, verze a aktualizace vpravo."""
        bar = ttk.Frame(self.root, padding=(10, 2, 10, 6))
        bar.pack(side="bottom", fill="x", before=self.nb)
        ttk.Separator(self.root).pack(side="bottom", fill="x", before=self.nb)
        ttk.Button(bar, text=T("Zkontrolovat aktualizace"),
                   command=lambda: self.check_updates(manual=True)).pack(side="right")
        ttk.Label(bar, text=T("verze {0}", APP_VERSION), foreground="gray").pack(side="right", padx=(10, 8))
        self.v_lang = tk.StringVar(value=LANG)
        for code, label in (("en", "EN"), ("cs", "CZ")):
            ttk.Radiobutton(bar, text=label, value=code, variable=self.v_lang,
                            command=self.change_lang).pack(side="right", padx=2)
        ttk.Label(bar, text="🌐").pack(side="right", padx=(12, 2))
        self.lbl_status = ttk.Label(bar, textvariable=self.v_status, anchor="w")
        self.lbl_status.pack(side="left", fill="x", expand=True)
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed, add="+")

    def _on_tab_changed(self, _e=None):
        """Stavový řádek dole ukazuje stav právě otevřené záložky."""
        try:
            idx = self.nb.index("current")
        except tk.TclError:
            return
        self.lbl_status.configure(textvariable=self.cmp.v_status if idx == 1 else self.v_status)

    def _build_update_bar(self):
        """Žlutý pruh nahoře s nabídkou nové verze (jako v Katalogu)."""
        bg, fg = "#fff4d6", "#5c4400"
        self.upd_bar = tk.Frame(self.root, bg=bg, highlightthickness=1, highlightbackground="#e8c766")
        self.upd_text = tk.Label(self.upd_bar, bg=bg, fg=fg, font=self.font_title)
        self.upd_text.pack(side="left", padx=(12, 16), pady=8)
        self.btn_upd = ttk.Button(self.upd_bar, text=T("Nainstalovat a restartovat"), command=self.show_update)
        self.btn_upd.pack(side="left")
        ttk.Button(self.upd_bar, text=T("Co je nového"), command=self.update_notes).pack(side="left", padx=6)
        ttk.Button(self.upd_bar, text=T("Skrýt"), command=self.upd_bar.pack_forget).pack(side="right", padx=8)

    def _after_update_notice(self):
        """Po aktualizaci krátce ukáže zelený pruh, na jakou verzi se aplikace aktualizovala."""
        prev = self.settings.get("app_version")
        self.settings["app_version"] = APP_VERSION
        if not prev or version_tuple(APP_VERSION) <= version_tuple(prev):
            return
        note = tk.Label(self.root, text=T("✓  Aplikace byla aktualizována na verzi {0}", APP_VERSION),
                        bg="#e5f4e4", fg="#1e6b2a", font=self.font_title, pady=8)
        note.pack(fill="x", padx=8, pady=(8, 0), before=self.nb)
        self.root.after(15000, note.destroy)

    def update_notes(self):
        info = getattr(self, "update_info", None)
        if info:
            messagebox.showinfo(APP_TITLE, T("Novinky ve verzi {0}:\n\n{1}", info["tag"].lstrip("vV"),
                                             (info["notes"].strip() or T("(bez popisu změn)"))[:3000]))

    def _build_ui(self):
        self._apply_style()
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_update_bar()
        # obsah záložek na ztmavené ploše; linka vede po vnějším okraji plochy a středem záložek
        r = self.tab_dup = tk.Frame(self.nb, bg=self.colors["pane"], bd=0, highlightthickness=0)
        self.nb.add(r, text=T("  Duplicity  "))
        self.tab_cmp = tk.Frame(self.nb, bg=self.colors["pane"], bd=0, highlightthickness=0)
        self.cmp = ComparePanel(self.tab_cmp, self.root, self.settings, self.colors)
        self.cmp.pack(fill="both", expand=True)
        self.nb.add(self.tab_cmp, text=T("  Porovnání dvou míst  "))

        top = ttk.Frame(r, padding=(10, 10, 10, 4))
        top.pack(fill="x")

        self.drop, inner = boxed(top, self.colors)
        self.drop.pack(fill="x")
        self.drop_inner = inner
        self.drop_label = ttk.Label(inner, text=T("⬇  Sem přetáhni disk nebo složku"), style="Big.TLabel",
                                    anchor="center")
        self.drop_label.pack(fill="x")
        self.roots_label = ttk.Label(inner, text="", anchor="center", foreground="gray")
        self.roots_label.pack(fill="x", pady=(4, 0))
        btns = ttk.Frame(inner)
        btns.pack(pady=(6, 0))
        ttk.Button(btns, text=T("Vybrat složku…"), command=self.choose_folder).pack(side="left", padx=3)
        ttk.Button(btns, text=T("Přidat další…"), command=lambda: self.choose_folder(add=True)).pack(side="left", padx=3)
        self.btn_leftovers = ttk.Button(btns, text=T("⚠ Pomocná složka"), command=self.open_leftovers)
        ttk.Button(btns, text=T("🔓 Odemknout a opravit práva…"),
                   command=lambda: PermsDialog(self.root, self.roots[0] if self.roots else "")).pack(side="left", padx=3)

        crit = ttk.Frame(r, padding=(10, 4))
        crit.pack(fill="x")
        ttk.Label(crit, text=T("Shoda:")).pack(side="left")
        for text, var in ((T("název"), self.v_name), (T("velikost"), self.v_size), (T("datum změny"), self.v_mtime),
                          (T("datum vytvoření"), self.v_btime), (T("ověřit obsah"), self.v_content)):
            ttk.Checkbutton(crit, text=text, variable=var, command=self.on_criteria_changed).pack(side="left", padx=4)
        ttk.Separator(crit, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(crit, text=T("Velikost:")).pack(side="left")
        cb = ttk.Combobox(crit, textvariable=self.v_minsize, values=[m[0] for m in MIN_SIZES],
                          state="readonly", width=14)
        cb.pack(side="left", padx=4)
        ttk.Checkbutton(crit, text=T("skryté soubory"), variable=self.v_hidden).pack(side="left", padx=4)
        ttk.Checkbutton(crit, text=T("uvnitř balíčků (.app, knihovny)"), variable=self.v_packages).pack(side="left", padx=4)
        self.btn_search = ttk.Button(crit, text=T("Hledat"), command=self.start_search)
        gm = ttk.Menubutton(crit, text="⚙ ▾")
        gmm = tk.Menu(gm, tearoff=False)
        gmm.add_command(label=T("Vyloučené složky…"), command=self.edit_exclude)
        gmm.add_command(label=T("Vymazat paměť otisků obsahu"), command=self.do_clear_cache)
        gmm.add_separator()
        gmm.add_command(label=T("Zkontrolovat aktualizace…"), command=lambda: self.check_updates(manual=True))
        self.v_autoupd = tk.BooleanVar(value=self.settings.get("check_updates", True))
        gmm.add_checkbutton(label=T("Kontrolovat aktualizace při spuštění"), variable=self.v_autoupd,
                            command=self.save)
        gm["menu"] = gmm
        gm.pack(side="right", padx=6)
        self.btn_search.pack(side="right")

        prog = ttk.Frame(r, padding=(10, 2))
        prog.pack(fill="x")
        self.pbar = ttk.Progressbar(prog, mode="determinate", maximum=1.0)
        self.pbar.pack(fill="x")

        mid = ttk.PanedWindow(r, orient="horizontal")
        mid.pack(fill="both", expand=True, padx=10, pady=4)

        left = ttk.Frame(mid)
        mid.add(left, weight=4)
        flt = ttk.Frame(left)
        flt.pack(fill="x", pady=(0, 4))
        ttk.Label(flt, text=T("Filtr:")).pack(side="left")
        e = ttk.Entry(flt, textvariable=self.v_filter, width=30)
        e.pack(side="left", padx=4)
        e.bind("<Return>", lambda ev: self.render())
        ttk.Button(flt, text=T("Použít"), command=self.render).pack(side="left")
        ttk.Checkbutton(flt, text=T("skrýt už sloučené klony"), variable=self.v_hide_merged,
                        command=self.render).pack(side="left", padx=10)
        ttk.Label(flt, text=T("Pohled:")).pack(side="left", padx=(6, 0))
        self.cb_view = ttk.Combobox(flt, textvariable=self.v_view, state="readonly", width=20,
                                    values=[T("Soubory"), T("Celé složky")])
        self.cb_view.pack(side="left", padx=4)
        self.cb_view.bind("<<ComboboxSelected>>", lambda e: self.render())
        ttk.Button(flt, text=T("Rozbalit vše"), command=lambda: self.expand_all(True)).pack(side="right")
        ttk.Button(flt, text=T("Sbalit vše"), command=lambda: self.expand_all(False)).pack(side="right", padx=4)

        cols = ("mark", "size", "mtime", "btime", "folder")
        tf, self.tree = framed_tree(left, self.colors, columns=cols, show="tree headings", selectmode="extended")
        tf.pack(fill="both", expand=True)
        # sloupec → (klíč řazení, popisek); kliknutí řadí, další kliknutí otočí směr (šipka jako ve Finderu)
        self.sort_cols = {"#0": ("name", T("Název")), "size": ("size", T("Velikost")),
                          "mtime": ("mtime", T("Změněno")), "btime": ("btime", T("Vytvořeno")),
                          "folder": ("wasted", T("Složka / ušetří"))}
        for col, (key, label) in self.sort_cols.items():
            self.tree.heading(col, text=label, anchor="e" if col == "size" else "w",
                              command=lambda k=key: self.set_sort(k))
        self.tree.heading("mark", text=T("Smazat"))
        self.update_sort_headings()
        self.tree.column("#0", width=280, stretch=True)
        self.tree.column("mark", width=60, anchor="center", stretch=False)
        self.tree.column("size", width=90, anchor="e", stretch=False)
        self.tree.column("mtime", width=125, stretch=False)
        self.tree.column("btime", width=125, stretch=False)
        self.tree.column("folder", width=380, stretch=True)
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        self._bold = bold
        self.tree.tag_configure("group", font=bold)
        self.tree.tag_configure("marked", foreground="#c0392b")
        self.tree.tag_configure("keep", foreground="#2e7d32")
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_tree_double)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Button-2>", self.on_context)       # pravé tlačítko na macOS
        self.tree.bind("<Button-3>", self.on_context)
        self.tree.bind("<Control-Button-1>", self.on_context)

        right = ttk.Frame(mid, padding=(10, 0, 0, 0))
        mid.add(right, weight=1)
        ttk.Label(right, text=T("Náhled"), font=self.font_title).pack(anchor="w")
        self.preview = ttk.Label(right, anchor="center")
        self.preview.pack(fill="x", pady=6)
        self.info = tk.Text(right, height=12, width=34, wrap="word", relief="flat", highlightthickness=0,
                            background=self.colors["pane"], borderwidth=0, font="TkDefaultFont")
        self.info.pack(fill="both", expand=True)
        self.info.configure(state="disabled")

        bot = ttk.Frame(r, padding=(10, 4, 10, 10))
        bot.pack(fill="x")
        ttk.Label(bot, text=T("Automaticky:")).pack(side="left")
        ttk.Combobox(bot, textvariable=self.v_strategy, values=list(STRATEGIES), state="readonly",
                     width=34).pack(side="left", padx=4)
        ttk.Button(bot, text=T("Označit"), command=self.do_auto_mark).pack(side="left")
        mb = ttk.Menubutton(bot, text=T("Další označení ▾"))
        m = tk.Menu(mb, tearoff=False)
        m.add_command(label=T("Označit vše ve složce…"), command=lambda: self.do_mark_folder(True))
        m.add_command(label=T("Odznačit vše ve složce…"), command=lambda: self.do_mark_folder(False))
        m.add_separator()
        m.add_command(label=T("Zrušit všechna označení"), command=self.clear_marks)
        mb["menu"] = m
        mb.pack(side="left", padx=4)
        self.lbl_marked = ttk.Label(bot, text=T("Označeno: 0"), font=bold)
        self.lbl_marked.pack(side="left", padx=12)

        ttk.Button(bot, text=T("Export CSV…"), command=self.do_export).pack(side="right")
        ttk.Button(bot, text=T("⚡ Uvolnit místo…"), command=self.do_free_space).pack(side="right", padx=4)
        rb = ttk.Menubutton(bot, text=T("Nahradit ▾"))
        rm = tk.Menu(rb, tearoff=False)
        rm.add_command(label=T("APFS klonem (doporučeno – soubor zůstane, místo se uvolní)"),
                       command=lambda: self.do_replace("clone"))
        rm.add_command(label=T("Pevným odkazem (hard link)"), command=lambda: self.do_replace("hardlink"))
        rm.add_command(label=T("Aliasem Finderu"), command=lambda: self.do_replace("alias"))
        rm.add_command(label=T("Symbolickým odkazem"), command=lambda: self.do_replace("symlink"))
        rb["menu"] = rm
        rb.pack(side="right", padx=4)
        ttk.Button(bot, text=T("Přesunout do…"), command=self.do_move).pack(side="right", padx=4)
        ttk.Button(bot, text=T("Do Koše"), command=self.do_trash).pack(side="right", padx=4)

        self.ctx = tk.Menu(r, tearoff=False)
        self.ctx.add_command(label=T("Zobrazit ve Finderu"), command=self.ctx_reveal)
        self.ctx.add_command(label=T("Otevřít"), command=self.ctx_open)
        self.ctx.add_command(label=T("Rychlý náhled (Quick Look)"), command=self.ctx_quicklook)
        self.ctx.add_separator()
        self.ctx.add_command(label=T("Ponechat tento, ostatní ve skupině označit"), command=self.ctx_keep_this)
        self.ctx.add_command(label=T("Označit / odznačit"), command=self.toggle_selected)
        self.ctx.add_separator()
        self.ctx.add_command(label=T("Vyloučit tuto složku z hledání"), command=self.ctx_exclude)
        self.ctx.add_command(label=T("Kopírovat cestu"), command=self.ctx_copy_path)

        # vzhled jako Katalog: ztmavená plocha, linka se zaoblenými rohy, spodní lišta
        self._pane_style(self.tab_dup)
        self._pane_style(self.tab_cmp)
        self._build_pane_outline()
        self._build_bottom_bar()
        self._after_update_notice()
        if self.settings.get("tab") == 1:
            self.nb.select(1)

    def _bind_keys(self):
        mod = "Command" if IS_MAC else "Control"
        self.root.bind(f"<{mod}-o>", lambda e: self.choose_folder())
        self.tree.bind("<space>", lambda e: (self.toggle_selected(), "break")[1])
        self.tree.bind(f"<{mod}-r>", lambda e: self.ctx_reveal())
        self.tree.bind("<Return>", lambda e: self.ctx_quicklook())
        self.root.bind("<Escape>", lambda e: self.cancel.set() if self.busy else None)

    def check_leftovers(self):
        """Na pozadí – spící nebo síťový disk nesmí zablokovat okno. Bez dialogu, jen tlačítko."""
        threading.Thread(target=lambda: self.q.put(("leftovers", staging_leftovers())), daemon=True).start()

    def show_leftovers(self, left):
        if not left:
            return
        self.leftovers = left
        self.btn_leftovers.pack(side="left", padx=3)
        if not self.busy and not self.groups:     # nepřepsat výsledek hledání
            self.v_status.set(T("⚠ Po minulém mazání s heslem správce zůstaly soubory v pomocné složce (nic se neztratilo) – tlačítko „Pomocná složka“ ji otevře."))

    def open_leftovers(self):
        for d in getattr(self, "leftovers", []):
            subprocess.run(["open", d])

    # ------------------------------------------------------------------ drag & drop
    def setup_dnd(self):
        if DND_IMPORT_ERROR is not None:
            self.drop_label.configure(text=T("Přetahování nefunguje – použij „Vybrat složku…“"))
            self.v_status.set(T("Knihovnu pro přetahování se nepodařilo načíst: {0}", DND_IMPORT_ERROR))
            return
        try:
            TkinterDnD._require(self.root)
            for w in (self.tab_dup, self.drop, self.drop_inner, self.drop_label, self.roots_label, self.tree):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self.on_drop)
                w.dnd_bind("<<DropEnter>>", self.on_drop_enter)
                w.dnd_bind("<<DropLeave>>", self.on_drop_leave)
        except Exception as exc:
            self.drop_label.configure(text=T("Přetahování nefunguje – použij „Vybrat složku…“"))
            self.v_status.set(T("Chyba přetahování: {0}", exc))
            return
        self.cmp.setup_dnd()

    def on_drop_enter(self, event):
        self.drop_label.configure(text=T("⬇  Pusť – spustím hledání"))
        return event.action

    def on_drop_leave(self, event):
        self.drop_label.configure(text=T("⬇  Sem přetáhni disk nebo složku"))
        return event.action

    def on_drop(self, event):
        self.drop_label.configure(text=T("⬇  Sem přetáhni disk nebo složku"))
        paths = list(self.root.tk.splitlist(event.data))
        self.set_roots(paths)
        return event.action

    def on_open_document(self, *paths):
        if self.nb.index("current") == 1:
            self.cmp.on_paths(list(paths))
        else:
            self.set_roots(list(paths))

    def set_roots(self, paths, add=False):
        dirs = []
        for p in paths:
            p = os.path.realpath(p)
            if os.path.isfile(p):
                p = os.path.dirname(p)
            if os.path.isdir(p) and p not in dirs:
                dirs.append(p)
        if not dirs:
            self.v_status.set(T("Přetáhni složku nebo disk (ne soubor)."))
            return
        if self.busy:
            self.v_status.set(T("Počkej, až doběhne hledání nebo akce, pak přetáhni znovu."))
            return
        if add:
            dirs = self.roots + dirs
        # bez duplicit a bez složek vnořených v jiných vybraných (i přes symlinky / jiný zápis cesty)
        kept = []
        for d in dirs:
            if any(is_inside(d, o) for o in kept):
                continue
            kept = [o for o in kept if not is_inside(o, d)] + [d]
        dirs = kept
        self.roots = dirs
        self.files, self.scan_sig = [], None
        self.update_roots_label()
        clouds = sorted({cloud_provider(d) for d in dirs} - {""})
        if clouds:
            messagebox.showinfo(APP_TITLE, T(
                "☁ Vybraná složka se synchronizuje s cloudem ({0}).\n\n"
                "• Smazání nebo přesun souboru se projeví i v cloudu a na všech ostatních zařízeních "
                "(u sdílených složek i ostatním lidem).\n"
                "• APFS klony, pevné odkazy, aliasy ani symlinky se tu dělat nebudou – cloud by soubory "
                "nahrál znovu a mohl by smazat jejich historii verzí.\n"
                "• Soubory jen v cloudu (nestažené) se kvůli porovnání nestahují.", ", ".join(clouds)))
        if not self.busy:
            self.start_search()

    def update_roots_label(self):
        names = []
        for d in self.roots:
            c = cloud_provider(d)
            names.append(("Macintosh HD" if d == "/" else d) + (f"   ☁ {c}" if c else ""))
        self.roots_label.configure(text="  •  ".join(names))

    def choose_folder(self, add=False):
        d = filedialog.askdirectory(title=T("Vyber složku nebo disk"))
        if d:
            self.set_roots([d], add=add)

    # ------------------------------------------------------------------ hledání
    def criteria(self):
        return {"name": self.v_name.get(), "size": self.v_size.get(), "mtime": self.v_mtime.get(),
                "btime": self.v_btime.get(), "content": self.v_content.get()}

    def scan_options(self):
        ms = dict(MIN_SIZES).get(self.v_minsize.get(), 1)
        return ScanOptions(hidden=self.v_hidden.get(), packages=self.v_packages.get(), min_size=ms,
                           exclude=self.exclude)

    def on_criteria_changed(self):
        if self.files and not self.busy:
            self.start_search()

    def start_search(self):
        if self.busy:
            self.cancel.set()
            return
        if not self.roots:
            self.v_status.set(T("Nejdřív přetáhni složku nebo disk."))
            return
        crit = self.criteria()
        if not any(crit.values()):
            messagebox.showinfo(APP_TITLE, T("Vyber aspoň jedno kritérium shody."))
            return
        opts = self.scan_options()
        sig = (tuple(self.roots), opts.signature())
        reuse = self.files if sig == self.scan_sig else None
        for f in self.files:                       # nové hledání = žádná stará označení
            f.marked = False
        self.save()
        self.set_busy(True)
        threading.Thread(target=self.worker_search, args=(list(self.roots), opts, crit, reuse, sig),
                         daemon=True).start()

    def worker_search(self, roots, opts, crit, reuse, sig):
        prog = lambda text, frac, path: self.q.put(("progress", text, frac))
        t0 = time.monotonic()
        try:
            if reuse is None:
                files, stats = scan_files(roots, opts, self.cancel, prog)
                self.q.put(("scanned", files, stats, sig))
            else:
                files, stats = reuse, None
            prog(T("Hledám shody…"), None, None)
            groups = group_files(files, crit)
            hits = None
            if crit["content"]:
                cache = DigestCache()
                cloud = []
                try:
                    groups = verify_groups(groups, self.cancel, prog, cache, cloud)
                finally:
                    cache.close()
                hits = (cache.hits, sum(cloud))
            prog(T("Zjišťuji, co už je sloučené APFS klonem…"), None, None)
            fill_clone_ids(groups, self.cancel)
            prog(T("Hledám celé duplicitní složky…"), None, None)
            folders = find_dup_folders(files, groups, self.cancel)
            self.q.put(("groups", groups, stats, len(files), time.monotonic() - t0, folders, hits))
        except Cancelled:
            self.q.put(("cancelled",))
        except Exception as exc:
            self.q.put(("error", f"{type(exc).__name__}: {exc}"))

    def set_busy(self, busy):
        self.busy = busy
        self.cancel.clear()
        self.btn_search.configure(text=T("Zastavit") if busy else T("Hledat"))
        if busy:
            self.pbar.configure(mode="indeterminate")
            self.pbar.start(12)
        else:
            self.pbar.stop()
            self.pbar.configure(mode="determinate", value=0)

    def poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                try:
                    self.handle(msg)
                except Exception:
                    log_exception(*sys.exc_info(), where=T("zpracování zprávy"))
                    if msg[0] in ("groups", "cancelled", "error", "action_done", "free_ready", "upd_fail"):
                        self.set_busy(False)
                    self.v_status.set(T("Vnitřní chyba – zapsáno do ~/Library/Logs/DuplicitniSoubory/chyby.log"))
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.poll)

    def handle(self, msg):
        kind = msg[0]
        if kind == "progress":
            _, text, frac = msg
            self.v_status.set(text)
            if frac is not None:
                if str(self.pbar.cget("mode")) != "determinate":
                    self.pbar.stop()
                    self.pbar.configure(mode="determinate")
                self.pbar.configure(value=frac)
        elif kind == "scanned":
            _, self.files, stats, self.scan_sig = msg
        elif kind == "groups":
            _, groups, stats, nfiles, secs, folders, hits = msg
            self.set_busy(False)
            self.groups = groups
            self.folder_groups = folders
            self.cb_view.configure(values=[T("Soubory"), T("Celé složky ({0})", len(folders))])
            if self.folders_view():
                self.v_view.set(T("Celé složky ({0})", len(folders)))
            self.render()
            wasted = sum(g.wasted for g in groups)
            extra = ""
            if stats:
                if stats["errors"]:
                    extra += T("  •  nepřístupné: {0} (Nastavení → Soukromí → Plný přístup k disku)", stats['errors'])
                if stats["hardlinks"]:
                    extra += T("  •  pevné odkazy přeskočeny: {0}", stats['hardlinks'])
                if stats.get("excluded"):
                    extra += T("  •  vyloučené složky: {0}", stats['excluded'])
            if hits and hits[0]:
                extra += T("  •  z paměti otisků: {0}", fmt_int(hits[0]))
            if hits and hits[1]:
                extra += T("  •  jen v cloudu (nestaženo, neověřeno): {0}", fmt_int(hits[1]))
            if folders:
                extra += T("  •  celé duplicitní složky: {0} (Pohled → Celé složky)", len(folders))
            ver = T(" (obsah ověřen)") if self.v_content.get() else T(" (obsah neověřen)")
            merged = sum(1 for g in groups if g.merged)
            if merged:
                extra = T("  •  už sloučeno klonem: {0} skupin", fmt_int(merged)) + extra
            self.v_status.set(T("Prohledáno {0} souborů za {1:.0f} s – {2} skupin duplicit{3}, lze uvolnit až {4}{5}", fmt_int(nfiles), secs, fmt_int(len(groups) - merged), ver, fmt_size(wasted), extra))
        elif kind == "leftovers":
            self.show_leftovers(msg[1])
        elif kind == "free_ready":
            self.free_ready(*msg[1:])
        elif kind == "update":
            self.on_update_info(*msg[1:])
        elif kind == "upd_done":
            msg[1].done(msg[2], msg[3])
        elif kind == "upd_ready":
            _, work, script, dmg = msg
            self.v_status.set(T("Instaluji – aplikace se za chvíli spustí znovu…"))
            self.save()
            install_update(self.root, script, dmg)
        elif kind == "upd_fail":
            self.set_busy(False)
            self.btn_upd.configure(state="normal")
            self.v_status.set("")
            messagebox.showerror(APP_TITLE, T("Aktualizaci se nepodařilo stáhnout: {0}\n\nAplikace běží dál "
                                              "beze změny. Zkus to později.", msg[1]))
        elif kind == "cancelled":
            self.set_busy(False)
            self.v_status.set("Zastaveno.")
        elif kind == "error":
            self.set_busy(False)
            self.v_status.set(T("Chyba: ") + msg[1])
            messagebox.showerror(APP_TITLE, msg[1])
        elif kind == "preview":
            _, path, png = msg
            if path == self.preview_req:
                self.show_preview_image(png)
        elif kind == "action_done":
            _, title, done_files, errors, ctx = msg
            self.set_busy(False)
            self.after_action(title, done_files, errors, ctx)

    # ------------------------------------------------------------------ výpis
    def folders_view(self):
        return self.cb_view.current() == 1

    def cur_groups(self):
        return self.folder_groups if self.folders_view() else self.groups

    def set_sort(self, key):
        if key == self.sort_key:
            self.sort_desc = not self.sort_desc
        else:                                  # nový sloupec: čísla a data od největšího, názvy od A
            self.sort_key, self.sort_desc = key, key != "name"
        self.update_sort_headings()
        self.render()

    def update_sort_headings(self):
        for col, (key, label) in self.sort_cols.items():
            arrow = ("  ▼" if self.sort_desc else "  ▲") if key == self.sort_key else ""
            self.tree.heading(col, text=label + arrow)

    @staticmethod
    def _file_key(key):
        return {"name": lambda f: norm_name(f.name), "size": lambda f: f.size, "mtime": lambda f: f.mtime,
                "btime": lambda f: f.btime, "wasted": lambda f: norm_name(f.path)}[key]

    def render(self):
        self.tree.delete(*self.tree.get_children())
        self.iid_file.clear()
        self.iid_group.clear()
        flt = norm_search(self.v_filter.get().strip())
        groups = self.cur_groups()
        if flt:
            cache = self.search_cache
            if len(cache) > 2_000_000:
                cache.clear()

            def ns(path):
                v = cache.get(path)
                if v is None:
                    v = cache[path] = norm_search(path)
                return v
            groups = [g for g in groups if any(flt in ns(f.path) for f in g.files)]
        hidden_merged = 0
        if self.v_hide_merged.get():
            before = len(groups)
            groups = [g for g in groups if not g.merged]
            hidden_merged = before - len(groups)
        self.hidden_merged = hidden_merged
        keys = {"wasted": lambda g: g.wasted, "size": lambda g: g.files[0].size,
                "name": lambda g: norm_name(g.name),
                "mtime": lambda g: max(f.mtime for f in g.files), "btime": lambda g: min(f.btime for f in g.files)}
        groups = sorted(groups, key=keys.get(self.sort_key, keys["wasted"]), reverse=self.sort_desc)
        fk = self._file_key(self.sort_key)
        for g in groups:                         # i soubory uvnitř skupiny podle stejného sloupce
            g.files.sort(key=fk, reverse=self.sort_desc and self.sort_key != "wasted")
        self.shown = groups
        for gi, g in enumerate(groups[:MAX_GROUPS_SHOWN]):
            self.insert_group(gi, g)
        if len(groups) > MAX_GROUPS_SHOWN:
            self.tree.insert("", "end", text=T("… a dalších {0} skupin (zúžit filtrem; automatické označení a akce platí pro všechny)", len(groups) - MAX_GROUPS_SHOWN))
        if self.hidden_merged:
            self.tree.insert("", "end", text=T("({0} skupin už sloučených APFS klonem je skryto)", self.hidden_merged))
        self.update_marked()

    def insert_group(self, gi, g, index="end"):
        giid = f"g{gi}"
        ok = T("  ✓ obsah") if g.verified else ""
        info = T("⧉ už sloučeno APFS klonem – zabírá místo jen jednou") if g.merged \
            else T("ušetří {0}{1}", fmt_size(g.wasted), ok)
        icon = ""
        if isinstance(g, FolderGroup):
            icon = "📁 "
            info = T("{0} souborů  •  {1}", fmt_int(g.nfiles), info)
        self.tree.insert("", index, iid=giid, open=len(self.shown) <= 200,
                         text=f"{icon}{len(g.files)}×  {g.name}",
                         values=("", fmt_size(g.files[0].size), "", "", info),
                         tags=("group",))
        self.iid_group[giid] = g
        clones = {}
        for f in g.files:
            if f.clone:
                clones[f.clone] = clones.get(f.clone, 0) + 1
        for fi, f in enumerate(g.files[:MAX_ROWS_PER_GROUP]):
            iid = f"{giid}_{fi}"
            self.iid_file[iid] = f
            self.tree.insert(giid, "end", iid=iid,
                             text=("🔒 " if f.locked else "") + ("📦 " if in_package(f) else "")
                             + ("☁ " if getattr(f, "dataless", False) else "")
                             + ("⧉ " if f.clone and clones.get(f.clone, 0) > 1 else "")
                             + f.name,
                             values=(CHECK_ON if f.marked else CHECK_OFF, fmt_size(f.size),
                                     fmt_date(f.mtime), fmt_date(f.btime), os.path.dirname(f.path)),
                             tags=("marked" if f.marked else "keep",))
        if len(g.files) > MAX_ROWS_PER_GROUP:
            self.tree.insert(giid, "end", iid=f"{giid}_vic",
                             text=T("… a dalších {0} souborů této skupiny (automatické označení a akce platí i pro ně)", len(g.files) - MAX_ROWS_PER_GROUP))

    def refresh_group(self, giid):
        g = self.iid_group.get(giid)
        if not g:
            return
        for iid in self.tree.get_children(giid):
            f = self.iid_file.get(iid)
            if f is None:
                continue
            self.tree.item(iid, values=(CHECK_ON if f.marked else CHECK_OFF, fmt_size(f.size),
                                        fmt_date(f.mtime), fmt_date(f.btime), os.path.dirname(f.path)),
                           tags=("marked" if f.marked else "keep",))

    def refresh_marks(self):
        for giid in self.iid_group:
            self.refresh_group(giid)
        self.update_marked()

    def update_marked(self):
        n, size = 0, 0
        for g in self.cur_groups():
            kept = {f.clone for f in g.files if not f.marked and f.clone}
            for f in g.files:
                if f.marked:
                    n += 1
                    if not (f.clone and f.clone in kept):   # klon ponechaného souboru nic neuvolní
                        size += f.size
        what = T("složek") if self.folders_view() else T("souborů")
        self.lbl_marked.configure(text=T("Označeno: {0} {1}, {2}", n, what, fmt_size(size)))

    def expand_all(self, open_):
        for giid in self.iid_group:
            self.tree.item(giid, open=open_)

    # ------------------------------------------------------------------ označování
    def toggle(self, iid, update=True):
        f = self.iid_file.get(iid)
        if f is None:
            return
        giid = self.tree.parent(iid)
        g = self.iid_group[giid]
        if self.guard():
            return
        if not f.marked and in_package(f):
            self.v_status.set(T("Soubor je uvnitř balíčku nebo skryté složky (např. knihovna Fotek, .git) – smazáním by se poškodila celá knihovna. Může zůstat jen jako ponechaný."))
            self.root.bell()
            return
        if not f.marked and sum(1 for x in g.files if not x.marked) <= 1:
            self.v_status.set(T("V každé skupině musí aspoň jeden soubor zůstat."))
            self.root.bell()
            return
        f.marked = not f.marked
        self.refresh_group(giid)
        if update:
            self.update_marked()

    def toggle_selected(self):
        for iid in self.tree.selection():
            if iid in self.iid_file:
                self.toggle(iid, update=False)
        self.update_marked()

    def on_tree_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "cell" and self.tree.identify_column(event.x) == "#1":
            iid = self.tree.identify_row(event.y)
            if iid in self.iid_file:
                self.toggle(iid)
                return "break"

    def on_tree_double(self, event):
        iid = self.tree.identify_row(event.y)
        if iid in self.iid_file:
            self.quicklook(self.iid_file[iid].path)
            return "break"

    def do_auto_mark(self):
        if not self.cur_groups() or self.guard():
            return
        strat = self.v_strategy.get()
        folder = None
        if STRATEGIES.get(strat) is None:
            folder = filedialog.askdirectory(title=T("Ve které složce soubory ponechat?"))
            if not folder:
                return
        n = auto_mark(self.cur_groups(), strat, prefer_folder=folder)
        self.refresh_marks()
        self.v_status.set(T("Označeno {0} souborů ({1}).", n, strat.lower()))
        self.save()

    def do_mark_folder(self, mark):
        if not self.cur_groups() or self.guard():
            return
        folder = filedialog.askdirectory(title=T("Vyber složku"))
        if folder:
            n = mark_in_folder(self.cur_groups(), folder, mark)
            self.refresh_marks()
            self.v_status.set(T("{0} {1} souborů ve složce {2}.", T("Označeno") if mark else T("Odznačeno"), n, folder))

    def clear_marks(self):
        if self.guard():
            return
        for g in self.cur_groups():
            for f in g.files:
                f.marked = False
        self.refresh_marks()

    # ------------------------------------------------------------------ kontextové menu
    def selected_file(self):
        sel = self.tree.selection()
        return self.iid_file.get(sel[0]) if sel else None

    def on_context(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            if iid in self.iid_file:
                self.ctx.tk_popup(event.x_root, event.y_root)
        return "break"

    def ctx_reveal(self):
        f = self.selected_file()
        if f:
            subprocess.run(["open", "-R", f.path])

    def ctx_open(self):
        f = self.selected_file()
        if f:
            subprocess.run(["open", f.path])

    def ctx_quicklook(self):
        f = self.selected_file()
        if f:
            self.quicklook(f.path)

    def quicklook(self, path):
        subprocess.Popen(["qlmanage", "-p", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def ctx_copy_path(self):
        f = self.selected_file()
        if f:
            self.root.clipboard_clear()
            self.root.clipboard_append(f.path)

    def ctx_keep_this(self):
        sel = self.tree.selection()
        if not sel or sel[0] not in self.iid_file:
            return
        if self.guard():
            return
        keep = self.iid_file[sel[0]]
        giid = self.tree.parent(sel[0])
        for f in self.iid_group[giid].files:
            f.marked = f is not keep and not in_package(f)
        self.refresh_group(giid)
        self.update_marked()

    # ------------------------------------------------------------------ náhled
    def on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid in self.iid_group and isinstance(self.iid_group[iid], FolderGroup):
            g = self.iid_group[iid]
            self.set_info(T("{0} shodné složky „{1}“\n\nV každé {2} souborů, {3}\nUšetří: {4}\nObsah: {5}\n\nPřed Košem se každá složka projde znovu a porovná soubor po souboru.", len(g.files), g.name, fmt_int(g.nfiles), fmt_size(g.files[0].size), fmt_size(g.wasted), T("ověřen – shodný") if g.verified else T("neověřen")))
            self.preview.configure(image="")
            return
        if iid in self.iid_group:
            g = self.iid_group[iid]
            self.set_info(T("{0} soubory se jménem „{1}“\n\nCelkem: {2}\nUšetří: {3}\nObsah: {4}", len(g.files), g.name, fmt_size(g.total), fmt_size(g.wasted), T("ověřen – shodný") if g.verified else T("neověřen (zapni „ověřit obsah“)")))
            self.preview.configure(image="")
            return
        f = self.iid_file.get(iid)
        if not f:
            return
        self.set_info(T("{0}\n\n{1}\n\nVelikost: {2} ({3} B)\nZměněno: {4}\nVytvořeno: {5}\n\n{6}", f.name, os.path.dirname(f.path), fmt_size(f.size), fmt_int(f.size), fmt_date(f.mtime), fmt_date(f.btime), T("Označen k odstranění") if f.marked else T("Ponechá se")))
        self.preview.configure(image="", text=T("…"))
        self.preview_req = f.path
        if IS_MAC:
            if getattr(self, "_preview_job", None):
                self.root.after_cancel(self._preview_job)
            self._preview_job = self.root.after(250, lambda p=f.path: self._start_preview(p))

    def _start_preview(self, path):
        self._preview_job = None
        if path == self.preview_req:
            threading.Thread(target=self.worker_preview, args=(path,), daemon=True).start()

    def worker_preview(self, path):
        out = tempfile.mkdtemp(dir=self.preview_dir)
        try:
            subprocess.run(["qlmanage", "-t", "-s", "320", "-o", out, path],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pass
        png = next((os.path.join(out, n) for n in os.listdir(out) if n.endswith(".png")), None)
        self.q.put(("preview", path, png))

    def show_preview_image(self, png):
        if not png:
            self.preview.configure(image="", text=T("(bez náhledu)"))
            return
        try:
            img = tk.PhotoImage(file=png)
            while img.width() > 320 or img.height() > 320:
                img = img.subsample(2)
            self.preview_img = img
            self.preview.configure(image=img, text="")
        except tk.TclError:
            self.preview.configure(image="", text=T("(bez náhledu)"))

    def set_info(self, text):
        self.info.configure(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("1.0", text)
        self.info.configure(state="disabled")

    # ------------------------------------------------------------------ akce
    def guard(self):
        """Během hledání nebo jiné akce nic neměnit – seznam by mohl být neaktuální."""
        if self.busy:
            self.root.bell()
            self.v_status.set(T("Počkej, až doběhne hledání nebo předchozí akce."))
            return True
        return False

    def get_plan(self):
        if self.guard():
            return []
        plan, skipped = plan_actions(self.cur_groups())
        if skipped:
            messagebox.showwarning(APP_TITLE, T("{0} skupin má označené všechny soubory – ty se přeskočí.", skipped))
        if not plan:
            messagebox.showinfo(APP_TITLE, T("Nic není označeno. Klikni do sloupce „Smazat“ nebo použij „Označit“ dole."))
        return plan

    def confirm(self, text, plan):
        n = sum(len(m) for _, m in plan)
        size = sum(f.size for _, m in plan for f in m)
        warn = (T("\n\n🛡 Před akcí se každý soubor porovná bajt po bajtu s ponechaným originálem. Pokud se liší, originál nejde celý přečíst (např. je poškozený) nebo se od hledání změnil, soubor zůstane beze změny."))
        cloud = sum(1 for _, m in plan for f in m if is_cloud(f.path))
        if cloud:
            warn += T("\n\n☁ {0} souborů je ve složce synchronizované s cloudem (OneDrive, Google Drive, iCloud…). "
                      "Smazáním nebo přesunem zmizí i z cloudu a ze všech zařízení – u sdílených složek i "
                      "ostatním lidem. Cloud je obvykle ještě nějakou dobu drží ve svém koši na webu.", cloud)
        return messagebox.askyesno(APP_TITLE, T("{0}\n\n{1} souborů, {2}.{3}\n\nPokračovat?", text, n, fmt_size(size), warn))

    def run_action(self, title, func, ctx=None):
        """func() → (hotové FileInfo, [(cesta, chyba)]). Chyby se v pozadí rozeberou (proč nejdou)."""
        self.set_busy(True)
        ctx = ctx or {}

        def work():
            try:
                done, errors = func()
            except AdminCancelled:
                done, errors = [], [(p, T("heslo správce nebylo zadáno")) for p in ctx.get("retry_paths", [])]
            except Exception as exc:
                log_exception(*sys.exc_info(), where="akce")
                done, errors = [], [("", str(exc))]
            try:
                if errors:
                    self.q.put(("progress", T("Zjišťuji, proč některé soubory nejdou zpracovat…"), None))
                    errors = diagnose_errors(errors, need_read=ctx.get("kind") == "replace")
            except Exception:
                log_exception(*sys.exc_info(), where="rozbor chyb")
                errors = [(p, m, [("other", str(m))]) for p, m in errors] if errors and len(errors[0]) == 2 else []
            finally:
                self.q.put(("action_done", title, done, errors, ctx))
        threading.Thread(target=work, daemon=True).start()

    def exec_action(self, ctx, files):
        """Provede akci z kontextu na zadaných souborech (v pracovním vlákně)."""
        kind = ctx["kind"]
        if kind == "ftrash":
            done, errors = [], []
            for i, d in enumerate(files, 1):
                if self.cancel.is_set():
                    break
                self.q.put(("progress", T("Ověřuji a dávám do Koše složku {0}/{1}: {2}", i, len(files), d.name),
                            (i - 1) / max(len(files), 1)))
                reason = Skip(T("chybí ponechaná složka"))
                for k in ctx["keepers"][d.path]:
                    reason = check_folder_pair(k, d)
                    if reason is None:
                        break
                if reason is not None:
                    errors.append((d.path, reason))
                    continue
                ok, err = trash_paths([d.path])
                if ok:
                    done.append(d)
                errors += err
            return done, errors
        strict = kind == "replace" and ctx.get("rkind") == "hardlink"
        label = {"trash": T("Do Koše"), "move": T("Přesouvám")}.get(kind, T("Nahrazuji"))
        done, errors = [], []
        n = len(files)
        # po dávkách 20 souborů: ověřit shodu s originálem a HNED provést akci (žádné dlouhé okno mezi)
        for start in range(0, n, 20):
            if self.cancel.is_set():
                break
            batch = files[start:start + 20]
            self.q.put(("progress", T("{0}: ověřuji a zpracovávám {1}–{2} z {3}", label, start + 1, start + len(batch), n),
                        start / max(n, 1)))
            # APFS klon si vlastní resource fork a metadata ponechá → rozdíl v nich nevadí
            same_dev = kind == "replace" and ctx.get("rkind") in ("clone", "hardlink")
            items = [(sorted(ctx["keepers"][f.path], key=lambda k, f=f: k.dev != f.dev) if same_dev
                      else ctx["keepers"][f.path], f) for f in batch]
            pairs, skipped = precheck(items, strict, self.cancel,
                                      own_rsrc_ok=kind == "replace" and ctx.get("rkind") == "clone",
                                      replace=kind == "replace")
            errors += skipped
            if self.cancel.is_set():
                break
            if kind == "trash":
                by_path = {f.path: f for _, f in pairs}
                ok, err = trash_paths(list(by_path))
                done += [by_path[p] for p in ok]
                errors += err
            elif kind == "move":
                for _, f in pairs:
                    try:
                        move_to_folder(f, ctx["dest"])
                        done.append(f)
                    except OSError as exc:
                        errors.append((f.path, _errmsg(exc)))
            else:
                d, err = run_replace(pairs, ctx["rkind"], self.cancel)
                done += d
                errors += err
        return done, errors

    @staticmethod
    def make_ctx(kind, plan, **kw):
        files = [f for _, m in plan for f in m]
        return dict(kind=kind, files={f.path: f for f in files},
                    keepers={f.path: keepers for keepers, m in plan for f in m}, **kw)

    def do_trash(self):
        if self.folders_view():
            return self.do_trash_folders()
        plan = self.get_plan()
        if not plan or not self.confirm(T("Přesunout označené soubory do Koše?\n(jdou vrátit: Koš → pravé tlačítko → Vrátit zpět)"), plan):
            return
        files = [f for _, m in plan for f in m]
        ctx = self.make_ctx("trash", plan)
        self.run_action(T("Přesun do Koše"), lambda: self.exec_action(ctx, files), ctx)

    def do_trash_folders(self):
        plan = self.get_plan()
        if not plan:
            return
        n = sum(len(m) for _, m in plan)
        size = sum(d.size for _, m in plan for d in m)
        if not messagebox.askyesno(
                APP_TITLE, T("Přesunout {0} označených složek ({1}) celé do Koše?\n\n🛡 Každá složka se těsně před tím projde znovu (i skryté a malé soubory) a každý soubor se porovná bajt po bajtu s ponechanou složkou. Když cokoli nesedí (jiný nebo navíc soubor, poškozený obsah), složka zůstane beze změny.", n, fmt_size(size))):
            return
        dirs = [d for _, m in plan for d in m]
        ctx = self.make_ctx("ftrash", plan)
        self.run_action(T("Složky do Koše"), lambda: self.exec_action(ctx, dirs), ctx)

    def do_move(self):
        if self.folders_view():
            messagebox.showinfo(APP_TITLE, T("V pohledu „Celé složky“ jde složky dát do Koše nebo nahradit APFS klony. Pro přesun přepni pohled na „Soubory“."))
            return
        plan = self.get_plan()
        if not plan:
            return
        dest = filedialog.askdirectory(title=T("Kam přesunout označené soubory?"))
        if not dest or not self.confirm(T("Přesunout označené soubory do „{0}“?\n(struktura podsložek se zachová)", dest), plan):
            return
        files = [f for _, m in plan for f in m]
        ctx = self.make_ctx("move", plan, dest=dest)
        self.run_action(T("Přesun"), lambda: self.exec_action(ctx, files), ctx)

    # ---------- opakování po chybě (zamčené soubory, oprávnění)
    def retry_unlocked(self, ctx, paths):
        files = [ctx["files"][p] for p in paths if p in ctx["files"]]
        kind = ctx["kind"]

        def func():
            undo = unlock_user([f.path for f in files])
            done = []
            try:
                done, err = self.exec_action(ctx, files)
            finally:
                # zamknout zpět složky i soubory, které se nezpracovaly; u APFS klonu i nový soubor.
                # Místa nahrazená pevným odkazem/aliasem/symlinkem ne (zámek by se přenesl na originál).
                links = kind == "replace" and ctx.get("rkind") != "clone"
                done_paths = {f.path for f in done}
                relock([(p, fl) for p, fl in undo if not (links and p in done_paths)])
            for f in done:
                f.locked = False
            return done, err
        self.run_action(T("Po odemčení"), func, dict(ctx, retry_paths=[f.path for f in files]))

    def retry_admin(self, ctx, paths):
        files = [ctx["files"][p] for p in paths if p in ctx["files"]]
        n = len(files)
        prompt = (T("Aplikace {0} potřebuje heslo správce, aby mohla přesunout {1} {2}, ke kterým nemáš oprávnění.", APP_TITLE, n, T("soubor") if n == 1 else T("soubory") if n < 5 else T("souborů")))
        self.v_status.set(T("Čekám na heslo správce…"))

        def func():
            prog = lambda text, frac, path: self.q.put(("progress", text, frac))
            pairs, skipped = precheck([(ctx["keepers"][f.path], f) for f in files], False, self.cancel, prog)
            if self.cancel.is_set():
                return [], skipped
            # těsně před akcí: ponechané soubory pořád existují a nezměnily se
            fresh = []
            for k, f in pairs:
                try:
                    st = os.stat(k.path)
                    if st.st_size == k.size and st.st_mtime == k.mtime:
                        fresh.append((k, f))
                        continue
                except OSError:
                    pass
                skipped.append((f.path, T("ponechaný soubor se mezitím změnil nebo zmizel – přeskočeno")))
            by_path = {f.path: f for _, f in fresh}
            if not by_path:
                return [], skipped
            if ctx["kind"] == "trash":
                ok, err = admin_trash(list(by_path), prompt)
                return [by_path[p] for p in ok], skipped + err
            pairs = []                             # přesun do složky
            for f in by_path.values():
                rel = os.path.relpath(f.path, f.root)
                root_name = os.path.basename(f.root.rstrip("/")) or "Disk"
                target = _unique(os.path.join(ctx["dest"], root_name, rel))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                pairs.append((f.path, target))
            moved = {s for s, _ in admin_move(pairs, prompt)}
            return ([by_path[p] for p in moved],
                    skipped + [(p, T("nepodařilo se ani s právy správce")) for p in by_path if p not in moved])
        self.run_action(T("S právy správce"), func, dict(ctx, retry_paths=[f.path for f in files]))

    def do_replace(self, kind):
        if self.folders_view():
            if kind != "clone":
                messagebox.showinfo(APP_TITLE, T("Celé složky jde nahradit jen APFS klonem (soubory zůstanou na místě, data se uloží jednou). Jiné náhrady jsou v pohledu „Soubory“."))
                return
            fplan = self.get_plan()
            if not fplan:
                return
            # složky → dvojice souborů na stejném relativním místě
            plan = []
            for keepers, marked in fplan:
                for d in marked:
                    for rel, f in d.files.items():
                        ks = [k.files[rel] for k in keepers if rel in k.files]
                        if ks:
                            plan.append((ks, [f]))
            if not plan:
                return
        else:
            plan = self.get_plan()
        if not plan:
            return
        texts = {
            "clone": T("Nahradit označené soubory APFS klonem ponechaného souboru?\n\nSoubory zůstanou na svých místech se stejným jménem, data se ale uloží jen jednou – místo se uvolní. Úprava jednoho souboru druhý nezmění. Funguje jen na disku APFS a ve stejném svazku; datum vytvoření se změní."),
            "hardlink": T("Nahradit označené soubory pevným odkazem?\n\nOba názvy pak ukazují na STEJNÁ data – úprava jednoho změní i druhý. Jen ve stejném svazku."),
            "alias": T("Nahradit označené soubory aliasem Finderu?\n\nPůvodní soubory se přesunou do Koše a na jejich místě vznikne alias. macOS se poprvé zeptá na povolení ovládat Finder."),
            "symlink": T("Nahradit označené soubory symbolickým odkazem?\n\nPůvodní soubory se přesunou do Koše. Odkaz přestane fungovat, když se ponechaný soubor přesune."),
        }
        if not self.confirm(texts[kind] + T("\n\nPřed náhradou se obsah porovná bajt po bajtu; rozdílné soubory se přeskočí."), plan):
            return
        files = [f for _, m in plan for f in m]
        ctx = self.make_ctx("replace", plan, rkind=kind, folders=self.folders_view())
        self.run_action(T("Náhrada ") + REPLACE_ACTIONS[kind][0], lambda: self.exec_action(ctx, files), ctx)

    def after_action(self, title, done_files, errors, ctx=None):
        _log_many([("PRESKOCENO" if any(c == "skipped" for c, _ in causes) else "CHYBA", p, "",
                    f"{title}: {m} | " + "; ".join(CAUSES[c][0] + (f" ({d})" if d else "") for c, d in causes))
                   for p, m, causes in errors])
        ctx = ctx or {}
        if ctx.get("kind") == "ftrash":            # celé složky v Koši → zmizí i jejich soubory
            gone = {id(d) for d in done_files}
            done_ids = {id(f) for d in done_files for f in d.files.values()}
            for fg in self.folder_groups:
                fg.files = [d for d in fg.files if id(d) not in gone]
            self.folder_groups = [fg for fg in self.folder_groups if len(fg.files) > 1 and not any(
                id(f) in done_ids for d in fg.files for f in d.files.values())]
        else:
            done_ids = {id(f) for f in done_files}
            # složky, ve kterých se něco změnilo, už nejsou úplné kopie → z pohledu složek pryč
            self.folder_groups = [fg for fg in self.folder_groups
                                  if not any(id(f) in done_ids for d in fg.files for f in d.files.values())]
        self.cb_view.configure(values=[T("Soubory"), T("Celé složky ({0})", len(self.folder_groups))])
        if self.folders_view():
            self.v_view.set(T("Celé složky ({0})", len(self.folder_groups)))
        # u náhrady aliasem/symlinkem na ponechaném souboru závisí odkazy → celou skupinu ze seznamu
        # vyřadit, aby ponechaný soubor nešel omylem označit a smazat
        linked = (ctx or {}).get("kind") == "replace" and (ctx or {}).get("rkind") in ("alias", "symlink")
        new_groups = []
        for g in self.groups:
            had = any(id(f) in done_ids for f in g.files)
            g.files = [f for f in g.files if id(f) not in done_ids]
            if len(g.files) > 1 and not (linked and had):
                new_groups.append(g)
        self.groups = new_groups
        self.files, self.scan_sig = [], None     # příště vše načíst znovu z disku
        self.render()
        saved = sum(f.size for f in done_files)
        skipped = sum(1 for _, _, causes in errors if any(c == "skipped" for c, _ in causes))
        what = T("složek") if ctx.get("kind") == "ftrash" else T("souborů")
        self.v_status.set(T("{0}: hotovo {1} {2} ({3}), přeskočeno ochranou {4}, chyb {5}. Záznam: ~/Library/Logs/DuplicitniSoubory", title, len(done_files), what, fmt_size(saved), skipped, len(errors) - skipped))
        if errors:
            FixDialog(self, title, errors, ctx)

    # ---------- ⚡ Uvolnit místo: ověřit, označit a nahradit APFS klony vše najednou
    def do_free_space(self):
        if self.guard():
            return
        cand = [g for g in self.groups if not g.merged]
        if IS_MAC:
            cand = [g for g in cand if fs_type(g.files[0].path) == "apfs"]
        if not cand:
            messagebox.showinfo(APP_TITLE, T("Není co uvolnit – žádné duplicity na disku APFS, které by ještě nebyly sloučené klonem. (Klony umí jen disk APFS.)"))
            return
        unverified = [g for g in cand if not g.verified]
        if unverified and not messagebox.askyesno(
                APP_TITLE, T("{0} skupin nemá ověřený obsah. Teď je ověřím (přečtou se celé soubory, už známé otisky se vezmou z paměti) a pak ukážu, kolik místa se uvolní.\n\nPokračovat?", len(unverified))):
            return
        self.set_busy(True)

        def work():
            try:
                fresh = []
                if unverified:
                    cache = DigestCache()
                    try:
                        prog = lambda t, fr, p: self.q.put(("progress", t, fr))
                        fresh = verify_groups(unverified, self.cancel, prog, cache)
                    finally:
                        cache.close()
                    fill_clone_ids(fresh, self.cancel)
                self.q.put(("free_ready", cand, unverified, fresh))
            except Cancelled:
                self.q.put(("cancelled",))
            except Exception as exc:
                log_exception(*sys.exc_info(), where=T("uvolnit místo"))
                self.q.put(("error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=work, daemon=True).start()

    def free_ready(self, cand, unverified, fresh):
        self.set_busy(False)
        if unverified:                              # neověřené skupiny nahradit ověřenými (mohou se rozdělit)
            old = {id(g) for g in unverified}
            self.groups = [g for g in self.groups if id(g) not in old] + fresh
            cand = [g for g in cand if id(g) not in old] + [g for g in fresh if not g.merged]
        self.render()
        cand = [g for g in cand if g.verified and not g.merged]
        strat = self.v_strategy.get()
        if STRATEGIES.get(strat) is None:
            strat = list(STRATEGIES)[0]
        before = {id(f): f.marked for g in cand for f in g.files}
        for g in cand:
            for f in g.files:
                f.marked = False
        _, save = auto_mark_per_volume(cand, strat)
        plan, _ = plan_actions(cand)
        self.refresh_marks()

        def restore():
            for g in cand:
                for f in g.files:
                    f.marked = before.get(id(f), False)
            self.refresh_marks()
        if not plan:
            restore()
            messagebox.showinfo(APP_TITLE, T("Po ověření obsahu nezbyly žádné skutečné duplicity k uvolnění (klon jde vytvořit jen mezi soubory na stejném disku)."))
            return
        n = sum(len(m) for _, m in plan)
        if not messagebox.askyesno(
                APP_TITLE, T("Uvolnit místo nahrazením {0} souborů v {1} skupinách APFS klonem?\n\nUvolní se až {2}.\n\nVšechny soubory zůstanou na svých místech se svými jmény, štítky i daty; jen jejich obsah se na disku uloží jednou. Na každém disku platí: {3}.\n\n🛡 Každý soubor se těsně před náhradou porovná bajt po bajtu s originálem – rozdílné se přeskočí.", fmt_int(n), fmt_int(len(plan)), fmt_size(save), strat)):
            restore()
            return
        files = [f for _, m in plan for f in m]
        ctx = self.make_ctx("replace", plan, rkind="clone")
        self.run_action(T("Uvolnit místo"), lambda: self.exec_action(ctx, files), ctx)

    # ---------- jazyk
    def change_lang(self):
        new = self.v_lang.get()
        if new == LANG:
            return
        self.save()
        if self.busy or self.cmp.busy:
            messagebox.showinfo(APP_TITLE, T("Jazyk se změní po příštím spuštění aplikace."))
            return
        if messagebox.askyesno(APP_TITLE, T("Pro změnu jazyka je potřeba aplikaci spustit znovu. Restartovat teď?")):
            restart_app(self.root)

    # ---------- aktualizace z GitHubu
    def check_updates(self, manual=False):
        def work():
            info = fetch_latest_release()
            self.q.put(("update", info, manual))
        threading.Thread(target=work, daemon=True).start()

    def on_update_info(self, info, manual):
        if info is None:
            if manual:
                messagebox.showwarning(APP_TITLE, T("Nepodařilo se spojit s GitHubem. Zkontroluj připojení k internetu."))
            return
        newer = version_tuple(info["tag"]) > version_tuple(APP_VERSION)
        if not newer:
            if manual:
                messagebox.showinfo(APP_TITLE, T("Máš nejnovější verzi ({0}).", APP_VERSION))
            return
        self.update_info = info
        self.upd_text.configure(text=T("🔔  Je k dispozici nová verze {0}  (máš {1})",
                                       info["tag"].lstrip("vV"), APP_VERSION))
        if not self.upd_bar.winfo_ismapped():
            self.upd_bar.pack(fill="x", padx=8, pady=(8, 0), before=self.nb)
        if manual or info["tag"] != self.settings.get("skip_version"):
            self.offer_update(info)

    def offer_update(self, info):
        """Jedna otázka: ANO = stáhnout, nainstalovat a restartovat bez dalšího zásahu."""
        notes = info["notes"].strip()
        notes = (notes[:600] + "…") if len(notes) > 600 else notes
        if not info.get("dmg_url"):
            messagebox.showinfo(APP_TITLE, T("Je k dispozici nová verze {0}, ale bez instalačního souboru. "
                                             "Otevřu stránku vydání.", info["tag"].lstrip("vV")))
            subprocess.run(["open", info["url"]])
            return
        if messagebox.askyesno(APP_TITLE, T("Je k dispozici nová verze {0} (máš {1}).\n\n{2}\n\n"
                                            "Nainstalovat ji teď? Aplikace se sama aktualizuje a spustí znovu.",
                                            info["tag"].lstrip("vV"), APP_VERSION, notes)):
            self.start_update(info)
        else:                                   # nenabízet znovu při spuštění; tlačítko nahoře zůstane
            self.skip_version(info["tag"])

    def start_update(self, info):
        if self.busy or self.cmp.busy or PermsDialog.active:
            if not messagebox.askyesno(APP_TITLE, T("Právě něco běží. Přerušit to a nainstalovat novou verzi?")):
                return
            self.cancel.set()
            self.cmp.cancel.set()
        self.set_busy(True)
        self.btn_upd.configure(state="disabled")
        self.v_status.set(T("Stahuji novou verzi {0}… Pak se aplikace zavře, aktualizuje a spustí znovu.",
                            info["tag"].lstrip("vV")))

        def work():
            try:
                self.q.put(("upd_ready", *prepare_update(info)))
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.q.put(("upd_fail", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def daily_update_check(self):
        if self.v_autoupd.get() and not getattr(self, "update_info", None):
            self.check_updates()
        self.root.after(24 * 3600 * 1000, self.daily_update_check)

    def show_update(self):
        if getattr(self, "update_info", None):
            self.offer_update(self.update_info)

    def skip_version(self, tag):
        self.settings["skip_version"] = tag
        self.save()

    # ---------- vyloučené složky a paměť otisků
    def edit_exclude(self):
        ExcludeDialog(self)

    def set_exclude(self, items):
        self.exclude = list(dict.fromkeys(i for i in items if i))
        self.files, self.scan_sig = [], None        # vyloučení se projeví při dalším hledání
        self.save()

    def ctx_exclude(self):
        f = self.selected_file()
        if not f:
            return
        d = f.path if isinstance(f, DirInfo) else os.path.dirname(f.path)
        if messagebox.askyesno(APP_TITLE, T("Vyloučit z hledání složku\n„{0}“?\n\n(Seznam jde upravit přes ⚙ → Vyloučené složky.)", d)):
            self.set_exclude(self.exclude + [d])
            if self.roots and not self.busy and messagebox.askyesno(APP_TITLE, T("Hledat znovu bez této složky?")):
                self.start_search()

    def do_clear_cache(self):
        if self.guard():
            return
        if messagebox.askyesno(APP_TITLE, T("Vymazat paměť otisků obsahu? Příští hledání s ověřením obsahu bude znovu číst všechny soubory.")):
            clear_digest_cache()
            self.v_status.set(T("Paměť otisků vymazána."))

    def do_export(self):
        if not self.groups:
            return
        path = filedialog.asksaveasfilename(title=T("Uložit přehled"), defaultextension=".csv",
                                            initialfile="duplicity.csv", filetypes=[("CSV", "*.csv")])
        if path:
            try:
                export_csv(self.shown or self.groups, path)
                self.v_status.set(T("Uloženo: {0}", path))
            except OSError as exc:
                messagebox.showerror(APP_TITLE, str(exc))

    # ------------------------------------------------------------------ konec
    def save(self):
        save_settings({"name": self.v_name.get(), "size": self.v_size.get(), "mtime": self.v_mtime.get(),
                       "btime": self.v_btime.get(), "content": self.v_content.get(),
                       "hidden": self.v_hidden.get(), "packages": self.v_packages.get(),
                       "minsize": self.v_minsize.get(), "strategy": self.v_strategy.get(),
                       "geometry": self.root.geometry(), "tab": self.nb.index("current"),
                       "exclude": self.exclude, "lang": self.v_lang.get(),
                       "sort_key": self.sort_key, "sort_desc": self.sort_desc,
                       "app_version": APP_VERSION,
                       "check_updates": self.v_autoupd.get(),
                       "skip_version": self.settings.get("skip_version", ""),
                       **self.cmp.settings()})

    def on_close(self):
        if (self.busy or self.cmp.busy or PermsDialog.active) and not messagebox.askyesno(
                APP_TITLE, T("Právě probíhá hledání, porovnání, oprava práv nebo akce se soubory.\n\nOpravdu ukončit? Zbytek akce se neprovede. Soubory se neztratí, ale může zůstat skrytý dočasný soubor (.dup-tmp-…) a oprava práv může zůstat rozpracovaná (vrátit ji jde tlačítkem „Vrátit opravu“).")):
            return
        self.cancel.set()
        self.cmp.cancel.set()
        self.save()
        shutil.rmtree(self.preview_dir, ignore_errors=True)
        self.root.destroy()


class PermsDialog:
    """Okno „Odemknout a opravit práva“ pro celou složku nebo disk: náhled → oprava → (vrácení)."""
    active = 0                       # počet právě běžících oprav (kvůli varování při ukončení)

    def __init__(self, root, path=""):
        self.root = root
        self.q = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.scan = None
        self.path = path
        me = _owner(os.getuid())
        w = self.win = tk.Toplevel(root)
        w.title(T("Odemknout a opravit práva"))
        w.transient(root)
        w.geometry("720x560")
        f = ttk.Frame(w, padding=14)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=T("Odemknout a opravit práva ve složce"), font=("Helvetica", 15, "bold")).pack(anchor="w")
        row = ttk.Frame(f)
        row.pack(fill="x", pady=(8, 4))
        self.lbl_path = ttk.Label(row, text=path or T("(vyber složku nebo disk)"), foreground="#444")
        self.lbl_path.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text=T("Vybrat…"), command=self.choose).pack(side="right")

        self.v_unlock = tk.BooleanVar(value=True)
        self.v_own = tk.BooleanVar(value=True)
        self.v_mode = tk.BooleanVar(value=True)
        self.v_acl = tk.BooleanVar(value=False)
        self.checks = []
        self.fixing = False
        for text, var in ((T("Odemknout zamčené soubory a složky"), self.v_unlock),
                          (T("Převzít vlastnictví – vše bude patřit uživateli „{0}“", me), self.v_own),
                          (T("Doplnit mi právo číst a zapisovat (práva ostatních se nemění)"), self.v_mode),
                          (T("Odstranit pravidla ACL (např. zákaz mazání) – jen pokud víš, že je nepotřebuješ"),
                           self.v_acl)):
            cb = ttk.Checkbutton(f, text=text, variable=var, command=self.start_scan)
            cb.pack(anchor="w", pady=1)
            self.checks.append(cb)

        self.pbar = ttk.Progressbar(f, mode="determinate", maximum=1.0)
        self.pbar.pack(fill="x", pady=(10, 2))
        self.v_status = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.v_status).pack(anchor="w")
        self.txt = tk.Text(f, height=12, wrap="word", relief="flat", background=root.cget("background"))
        self.txt.pack(fill="both", expand=True, pady=(6, 0))

        bf = ttk.Frame(f)
        bf.pack(fill="x", pady=(10, 0))
        ttk.Button(bf, text=T("Zavřít"), command=self.close).pack(side="right")
        self.btn_fix = ttk.Button(bf, text=T("Opravit"), command=self.do_fix, state="disabled")
        self.btn_fix.pack(side="right", padx=6)
        self.btn_undo = ttk.Button(bf, text=T("Vrátit poslední opravu…"), command=self.do_undo)
        self.btn_undo.pack(side="left")
        self.update_undo()
        w.protocol("WM_DELETE_WINDOW", self.close)
        w.bind("<Escape>", lambda e: self.close())
        if DND_IMPORT_ERROR is None:
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self.on_drop)
            except Exception:
                pass
        self.poll()
        if path:
            self.start_scan()

    def set_text(self, t):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", t)
        self.txt.configure(state="disabled")

    def on_drop(self, event):
        paths = [p for p in self.root.tk.splitlist(event.data) if os.path.isdir(p)]
        if paths:
            self.set_path(paths[0])
        return event.action

    def choose(self):
        d = filedialog.askdirectory(title=T("Ve které složce nebo disku opravit práva?"), parent=self.win)
        if d:
            self.set_path(d)

    def set_path(self, d):
        self.path = os.path.abspath(d)
        self.lbl_path.configure(text=self.path)
        self.start_scan()

    def opts(self):
        return PermOptions(self.v_unlock.get(), self.v_own.get(), self.v_mode.get(), self.v_acl.get())

    def update_undo(self):
        u = last_undo()
        if u:
            when = os.path.basename(u[0])[:16].replace(".", ":", 1)
            self.btn_undo.configure(state="normal", text=T("Vrátit opravu z {0} ({1} položek)…", when, fmt_int(u[2])))
        else:
            self.btn_undo.configure(state="disabled", text=T("Vrátit poslední opravu…"))

    def _rescan_if_open(self):
        try:
            if self.win.winfo_exists():
                self.start_scan()
        except tk.TclError:
            pass

    def start_scan(self):
        if not self.path or self.fixing:          # během opravy nic nepřerušovat
            return
        if self.busy:
            self.cancel.set()
            self.win.after(200, self._rescan_if_open)
            return
        why = perms_forbidden(self.path)
        if why:
            self.scan = None
            self.btn_fix.configure(state="disabled")
            self.v_status.set("")
            self.set_text(T("⛔ Tady opravu práv nelze udělat: {0}.", why))
            return
        self.set_busy(True)
        opts, path = self.opts(), self.path
        prog = lambda t, fr, p: self.q.put(("progress", t, fr))

        def work():
            try:
                self.q.put(("scanned", perm_scan(path, opts, self.cancel, prog)))
            except Cancelled:
                self.q.put(("idle", ""))
            except Exception as exc:
                log_exception(*sys.exc_info(), where=T("kontrola práv"))
                self.q.put(("idle", T("Chyba: {0}", exc)))
        threading.Thread(target=work, daemon=True).start()

    def set_busy(self, busy, fixing=False):
        was = self.fixing
        self.busy = busy
        self.fixing = busy and fixing
        PermsDialog.active += int(self.fixing) - int(was)
        for cb in self.checks:
            cb.configure(state="disabled" if self.fixing else "normal")
        self.cancel.clear()
        self.btn_fix.configure(state="disabled")
        if busy:
            self.pbar.configure(mode="indeterminate")
            self.pbar.start(12)
        else:
            self.pbar.stop()
            self.pbar.configure(mode="determinate", value=0)

    def describe(self, sc):
        ln = [T("Prohledáno {0} položek.", fmt_int(sc.items))]
        if sc.fstype in ("exfat", "msdos", "ntfs", "smbfs", "webdav"):
            ln.append(T("Disk typu {0}: vlastníci a zámky se tu neukládají (nebo je mění server), oprava nemusí mít účinek.", sc.fstype))
        if sc.noowners:
            ln.append(T("Disk má zapnuté „Ignorovat vlastnictví“ – vlastník se neřeší, přístup má každý."))
        ln.append("")
        ln.append(T("🔒 Zamčené: {0}", fmt_int(sc.locked)) + (T("   (z toho systémový zámek: {0})", fmt_int(sc.sys_locked))
                                                         if sc.sys_locked else ""))
        ln.append(T("👤 Patří jinému uživateli / systému: {0}", fmt_int(sc.foreign)))
        ln.append(T("✋ Bez mého práva číst a zapisovat: {0}", fmt_int(sc.no_rights)))
        if sc.unreadable:
            ln.append(T("🚪 Nepřístupné složky (obsah neznámý): {0}", fmt_int(len(sc.unreadable))))
        ln.append("")
        if not sc.problems:
            ln.append(T("✅ S vybranými volbami tu není co opravit."))
        else:
            ln.append(T("Opraví se {0} položek", fmt_int(len(sc.records)))
                      + (T(" + obsah {0} nepřístupných složek", fmt_int(len(sc.unreadable))) if sc.unreadable else "") + ".")
            if sc.needs_admin or sc.unreadable:
                ln.append(T("Bude potřeba heslo správce."))
            ln.append(T("Původní stav se uloží – opravu půjde vrátit tlačítkem vlevo dole."))
            if self.v_acl.get():
                ln.append(T("Pravidla ACL se odstraní u všeho v této složce; jejich vrácení není možné."))
        return "\n".join(ln)

    def poll(self):
        try:
            self._poll()
        except Exception:
            log_exception(*sys.exc_info(), where=T("okno práv"))
            self.set_busy(False)
        finally:
            try:
                if self.win.winfo_exists():
                    self.win.after(100, self.poll)
            except tk.TclError:
                pass

    def _poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == "progress":
                    self.v_status.set(m[1])
                    if m[2] is not None:
                        self.pbar.stop()
                        self.pbar.configure(mode="determinate", value=m[2])
                elif m[0] == "scanned":
                    self.set_busy(False)
                    self.scan = m[1]
                    self.v_status.set("")
                    self.set_text(self.describe(self.scan))
                    self.btn_fix.configure(state="normal" if self.scan.problems or self.v_acl.get() else "disabled")
                elif m[0] == "fixed":
                    self.set_busy(False)
                    self.update_undo()
                    self.v_status.set(m[1])
                    self.start_scan()                       # zkontrolovat znovu, co zbylo
                elif m[0] == "idle":
                    self.set_busy(False)
                    self.v_status.set(m[1])
        except queue.Empty:
            pass

    def do_fix(self):
        sc = self.scan
        if not sc or self.busy:
            return
        pw = T("\n\nmacOS se zeptá na heslo správce.") if sc.needs_admin or sc.unreadable else ""
        if not messagebox.askyesno(APP_TITLE, T("Opravit práva ve složce\n„{0}“?\n\n{1} položek se odemkne / převezme / dostane práva.{2}\n\nPůvodní stav se uloží pro vrácení.", sc.root, fmt_int(len(sc.records)), pw),
                                   parent=self.win):
            return
        self.set_busy(True, fixing=True)
        opts = self.opts()
        prog = lambda t, fr, p: self.q.put(("progress", t, fr))
        prompt = T("Aplikace {0} potřebuje heslo správce k opravě práv ve složce „{1}“.", APP_TITLE, os.path.basename(sc.root))

        def work():
            try:
                undo, errs = perm_fix(sc, opts, prompt, self.cancel, prog)
                msg = T("Hotovo.") + (T(" Nepodařilo se: {0}.", errs) if errs else "")
            except AdminCancelled:
                msg = T("Zrušeno – heslo nebylo zadáno.")
            except Exception as exc:
                log_exception(*sys.exc_info(), where=T("oprava práv"))
                msg = T("Chyba: {0}", exc)
            self.q.put(("fixed", msg))
        threading.Thread(target=work, daemon=True).start()

    def do_undo(self):
        u = last_undo()
        if not u or self.busy:
            return
        if not messagebox.askyesno(APP_TITLE, T("Vrátit vlastníky, práva a zámky ve složce\n„{0}“\ndo stavu před opravou ({1} položek)?", u[1], fmt_int(u[2])), parent=self.win):
            return
        self.set_busy(True, fixing=True)

        def work():
            try:
                n = perm_restore(u[0], T("Aplikace {0} potřebuje heslo správce k vrácení práv.", APP_TITLE))
                msg = T("Vráceno {0} položek.", fmt_int(n))
            except AdminCancelled:
                msg = T("Zrušeno – heslo nebylo zadáno.")
            except Exception as exc:
                log_exception(*sys.exc_info(), where=T("oprava práv"))
                msg = T("Chyba: {0}", exc)
            self.q.put(("fixed", msg))
        threading.Thread(target=work, daemon=True).start()

    def close(self):
        if self.fixing and not messagebox.askyesno(APP_TITLE, T("Oprava práv ještě běží. Zavřít okno? Oprava doběhne na pozadí."), parent=self.win):
            return
        self.win.destroy()


class ExcludeDialog:
    """Seznam složek, které se při hledání duplicit přeskočí."""

    def __init__(self, app):
        self.app = app
        w = self.win = tk.Toplevel(app.root)
        w.title(T("Vyloučené složky"))
        w.transient(app.root)
        w.geometry("620x420")
        f = ttk.Frame(w, padding=12)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=T("Tyto složky se při hledání duplicit přeskočí."), font=("Helvetica", 13, "bold")
                  ).pack(anchor="w")
        ttk.Label(f, text=T("Cesta (např. /Volumes/Backup disk 2/Horus) = jen ta složka.  Samotný název (např. node_modules) = každá složka tohoto jména."), wraplength=590,
                  foreground="#555").pack(anchor="w", pady=(2, 8))
        lf = ttk.Frame(f)
        lf.pack(fill="both", expand=True)
        self.lb = tk.Listbox(lf, selectmode="extended", activestyle="none")
        ys = ttk.Scrollbar(lf, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=ys.set)
        self.lb.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        for x in app.exclude:
            self.lb.insert("end", x)
        bf = ttk.Frame(f)
        bf.pack(fill="x", pady=(8, 0))
        ttk.Button(bf, text=T("Přidat složku…"), command=self.add_folder).pack(side="left")
        self.v_name = tk.StringVar()
        e = ttk.Entry(bf, textvariable=self.v_name, width=18)
        e.pack(side="left", padx=(12, 2))
        e.bind("<Return>", lambda ev: self.add_name())
        ttk.Button(bf, text=T("Přidat název"), command=self.add_name).pack(side="left")
        ttk.Button(bf, text=T("Odebrat"), command=self.remove).pack(side="left", padx=12)
        ttk.Button(bf, text=T("Hotovo"), command=self.close).pack(side="right")
        w.protocol("WM_DELETE_WINDOW", self.close)
        w.bind("<Escape>", lambda ev: self.close())

    def add_folder(self):
        d = filedialog.askdirectory(title=T("Kterou složku vyloučit?"), parent=self.win)
        if d and d not in self.lb.get(0, "end"):
            self.lb.insert("end", os.path.realpath(d))

    def add_name(self):
        n = self.v_name.get().strip().strip("/")
        if n and "/" not in n and n not in self.lb.get(0, "end"):
            self.lb.insert("end", n)
        self.v_name.set("")

    def remove(self):
        for i in reversed(self.lb.curselection()):
            self.lb.delete(i)

    def close(self):
        new = list(self.lb.get(0, "end"))
        changed = new != self.app.exclude
        self.app.set_exclude(new)
        self.win.destroy()
        if changed:
            self.app.v_status.set(T("Seznam vyloučených složek změněn – projeví se při dalším hledání."))


class UpdateDialog:
    """Nabídka nové verze z GitHubu."""

    def __init__(self, app, info):
        self.app, self.info = app, info
        w = self.win = tk.Toplevel(app.root)
        w.title(T("Aktualizace"))
        w.transient(app.root)
        w.geometry("560x420")
        f = ttk.Frame(w, padding=14)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=T("Je k dispozici nová verze {0}", info["tag"].lstrip("vV")),
                  font=("Helvetica", 15, "bold")).pack(anchor="w")
        ttk.Label(f, text=T("Máš verzi {0}.", APP_VERSION), foreground="#555").pack(anchor="w", pady=(2, 8))
        txt = tk.Text(f, height=12, wrap="word", relief="flat", background=app.root.cget("background"))
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", info["notes"][:4000] or T("(bez popisu změn)"))
        txt.configure(state="disabled")
        self.v_status = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.v_status, wraplength=520).pack(anchor="w", pady=(6, 0))
        bf = ttk.Frame(f)
        bf.pack(fill="x", pady=(10, 0))
        ttk.Button(bf, text=T("Později"), command=w.destroy).pack(side="right")
        if info.get("dmg_url"):
            ttk.Button(bf, text=T("Nainstalovat a restartovat"), command=self.install).pack(side="right", padx=6)
        ttk.Button(bf, text=T("Otevřít stránku vydání"),
                   command=lambda: subprocess.run(["open", info["url"]])).pack(side="right")
        ttk.Button(bf, text=T("Tuto verzi přeskočit"), command=self.skip).pack(side="left")
        w.bind("<Escape>", lambda e: w.destroy())

    def skip(self):
        self.app.skip_version(self.info["tag"])
        self.win.destroy()

    def install(self):
        if (self.app.busy or self.app.cmp.busy or PermsDialog.active) and not messagebox.askyesno(
                APP_TITLE, T("Právě něco běží. Přerušit to a nainstalovat novou verzi?"), parent=self.win):
            return
        self.app.cancel.set()
        self.app.cmp.cancel.set()
        self.app.save()
        install_update(self.app.root)

    def download(self):
        self.btn_dl.configure(state="disabled")
        self.v_status.set(T("Stahuji {0}…", self.info["dmg_name"]))

        def work():
            try:
                path = download_update(self.info)
                msg = ("ok", path)
            except (OSError, subprocess.TimeoutExpired) as exc:
                msg = ("err", str(exc))
            self.app.q.put(("upd_done", self, *msg))     # Tk se smí volat jen z hlavního vlákna
        threading.Thread(target=work, daemon=True).start()

    def done(self, kind, value):
        try:
            if kind == "ok":
                subprocess.run(["open", value])
                self.v_status.set(T("Staženo do {0}. Otevřel se instalační disk – zavři tuto aplikaci a "
                                    "přetáhni novou verzi do složky Aplikace (nahradit).", value))
            else:
                self.v_status.set(T("Stažení se nepodařilo: {0}", value))
                self.btn_dl.configure(state="normal")
        except tk.TclError:
            pass


class FixDialog:
    """Okno po neúspěšné akci: proč soubory nešly zpracovat a co s tím."""

    def __init__(self, app, title, errors, ctx):
        self.app, self.ctx, self.errors = app, ctx, errors
        kind = ctx.get("kind")
        by_class = {"user": [], "admin": [], "perm": [], "tcc": [], "none": []}
        counts = {}
        for p, m, causes in errors:
            by_class[fix_class(causes)].append(p)
            for c, _ in causes:
                counts[c] = counts.get(c, 0) + 1
        self.user_paths = by_class["user"]
        self.admin_paths = by_class["user"] + by_class["admin"] if kind in ("trash", "move") else []

        w = self.win = tk.Toplevel(app.root)
        w.title(APP_TITLE)
        w.transient(app.root)
        w.geometry("760x560")
        frm = ttk.Frame(w, padding=14)
        frm.pack(fill="both", expand=True)
        n = len(errors)
        ttk.Label(frm, text=T("{0}: {1} {2} se nepodařilo zpracovat", title, n, T("soubor") if n == 1 else T("soubory") if n < 5 else T("souborů")), font=("Helvetica", 15, "bold")).pack(anchor="w")
        summ = "   ".join(f"{CAUSES[c][0]}: {k}" for c, k in sorted(counts.items(), key=lambda x: -x[1]))
        ttk.Label(frm, text=summ, wraplength=720).pack(anchor="w", pady=(6, 8))

        tips = []
        if self.user_paths:
            tips.append(T("🔒 Zamčené soubory (Finder → Informace → Zamčeno) můžeš odemknout sám. Složky, které byly zamčené, aplikace po akci zase zamkne."))
        if by_class["admin"]:
            if kind in ("trash", "move"):
                tips.append(T("👤 Soubory patří jinému uživateli nebo systému – typicky kopie ze starého Macu, z jiného disku nebo ze zálohy. Po zadání hesla správce je aplikace přesune")
                            + (T(" do Koše přes pomocnou složku (Vrátit zpět z Koše je pak vrátí do ní, ne na původní místo).") if kind == "trash" else "."))
            else:
                tips.append(T("👤 Soubory patří jinému uživateli nebo systému. Náhrada s heslem správce není možná – použij u nich „Do Koše“, tam se heslo nabídne."))
        if by_class["perm"]:
            tips.append(T("👤 Některé soubory nejde přečíst, takže se nedá ověřit shoda s originálem. Použij „Opravit práva ve složce…“ (převezme vlastnictví a doplní práva) a akci zopakuj."))
        if by_class["tcc"]:
            tips.append(T("🛡 macOS aplikaci nepustil do chráněného místa. Zapni ji v Nastavení systému → Soukromí a zabezpečení → Plný přístup k disku a aplikaci spusť znovu."))
        if counts.get("skipped"):
            tips.append(T("🛡 Přeskočené soubory zůstaly beze změny – aplikace je záměrně nezpracovala (důvod je u každého v seznamu). Nic se neztratilo."))
        if any(c in counts for c in ("ro", "sip", "missing", "other")):
            tips.append(T("⛔ Disk jen pro čtení (např. NTFS z Windows) nebo soubory chráněné systémem – ty aplikace změnit nemůže."))
        ttk.Label(frm, text="\n\n".join(tips), wraplength=720, justify="left").pack(anchor="w", pady=(0, 8))

        tf = ttk.Frame(frm)
        tf.pack(fill="both", expand=True)
        txt = tk.Text(tf, height=10, wrap="none", font=("Menlo", 11))
        ys = ttk.Scrollbar(tf, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=ys.set)
        txt.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        self.listing = []
        for p, m, causes in errors:
            why = "; ".join(CAUSES[c][0] + (f" ({d})" if d else "") for c, d in causes)
            self.listing.append(f"{p}\n    {why}")
        txt.insert("1.0", "\n".join(self.listing[:500]) + (T("\n… a dalších {0}", n - 500) if n > 500 else ""))
        txt.configure(state="disabled")

        bf = ttk.Frame(frm)
        bf.pack(fill="x", pady=(10, 0))
        ttk.Button(bf, text=T("Zavřít"), command=self.close).pack(side="right")
        if self.admin_paths:
            ttk.Button(bf, text=T("Zkusit s heslem správce ({0})", len(self.admin_paths)),
                       command=self.do_admin).pack(side="right", padx=6)
        if self.user_paths and "files" in ctx:
            b = ttk.Button(bf, text=T("Odemknout a zkusit znovu ({0})", len(self.user_paths)), command=self.do_user)
            b.pack(side="right")
            b.focus_set()
        if by_class["tcc"] and IS_MAC:
            ttk.Button(bf, text=T("Otevřít Plný přístup k disku"),
                       command=lambda: subprocess.run(["open", FDA_URL])).pack(side="left")
        ttk.Button(bf, text=T("Kopírovat seznam"), command=self.copy).pack(side="left", padx=6)
        roots = [ctx["files"][p].root for p, _, _ in errors if p in ctx.get("files", {})]
        if roots:
            ttk.Button(bf, text=T("Opravit práva ve složce…"),
                       command=lambda: (self.close(), PermsDialog(app.root, roots[0]))).pack(side="left")
        w.bind("<Escape>", lambda e: self.close())

        def grab():
            try:
                w.grab_set()
            except tk.TclError:          # okno ještě není vidět
                pass
        w.after(150, grab)

    def copy(self):
        self.win.clipboard_clear()
        self.win.clipboard_append("\n".join(self.listing))

    def close(self):
        try:
            self.win.grab_release()
        except tk.TclError:
            pass
        self.win.destroy()

    def do_user(self):
        self.close()
        self.app.retry_unlocked(self.ctx, self.user_paths)

    def do_admin(self):
        self.close()
        self.app.retry_admin(self.ctx, self.admin_paths)


STATUS_LABEL = {"onlyA": T("→ chybí v B"), "onlyB": T("← chybí v A"), "diff": T("≠ liší se"),
                "type": T("⚠ jiný typ"), "same": T("= stejné")}
VIEWS = {T("Rozdíly (vše kromě stejných)"): ("onlyA", "onlyB", "diff", "type"),
         T("Jen v A (chybí v B)"): ("onlyA",), T("Jen v B (chybí v A)"): ("onlyB",),
         T("Liší se"): ("diff", "type"), T("Stejné"): ("same",), T("Vše"): ("onlyA", "onlyB", "diff", "type", "same")}
MAX_ROWS_SHOWN = 10000


def _inv(d):
    return {v: k for k, v in d.items()}


class ComparePanel(ttk.Frame):
    """Karta „Porovnání dvou míst“: co je jen v A, jen v B, co se liší – a doplnění kopírováním."""

    def __init__(self, master, root, s, colors=None):
        super().__init__(master)
        self.colors = colors or {"pane": "#fafafa", "win": "#ffffff", "border": "#b4b4b4"}
        self.root = root
        self.q = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.paths = {"A": s.get("cmp_a", ""), "B": s.get("cmp_b", "")}
        self.items = []
        self.iid_item = {}
        self.v_layout = tk.StringVar(value=LAYOUT_MODES.get(s.get("cmp_layout"), LAYOUT_MODES["path"]))
        self.v_match = tk.StringVar(value=MATCH_MODES.get(s.get("cmp_match"), MATCH_MODES["quick"]))
        self.v_hidden = tk.BooleanVar(value=s.get("cmp_hidden", True))
        self.v_view = tk.StringVar(value=list(VIEWS)[0])
        self.v_dir = tk.StringVar(value=DIRECTIONS.get(s.get("cmp_dir"), DIRECTIONS["both"]))
        self.v_policy = tk.StringVar(value=CONFLICT_POLICIES["skip"])
        self.v_verify = tk.BooleanVar(value=True)      # ověřování kopií je vždy zapnuté při startu
        self.cmp_params = None          # (A, B, uspořádání, shoda) posledního porovnání
        self.v_status = tk.StringVar(value=T("Přetáhni dvě místa (složky nebo disky) – do A a do B. Můžeš přetáhnout i obě najednou."))
        self._build()
        self._update_zone_labels()
        self.after(100, self.poll)

    # ----------------------------------------------------------------- UI
    def _build(self):
        zones = ttk.Frame(self, padding=(10, 10, 10, 4))
        zones.pack(fill="x")
        zones.columnconfigure(0, weight=1)
        zones.columnconfigure(2, weight=1)
        self.zone, self.zone_lbl, self.zone_path = {}, {}, {}
        for col, side in ((0, "A"), (2, "B")):
            z, zi = boxed(zones, self.colors, padding=10)
            z.grid(row=0, column=col, sticky="nsew")
            lbl = ttk.Label(zi, text=T("⬇  Místo {0}", side), style="Big.TLabel", anchor="center")
            lbl.pack(fill="x")
            pth = ttk.Label(zi, text="", anchor="center", foreground="gray")
            pth.pack(fill="x", pady=(3, 4))
            ttk.Button(zi, text=T("Vybrat…"), command=lambda s=side: self.choose(s)).pack()
            self.zone[side], self.zone_lbl[side], self.zone_path[side] = z, lbl, pth
            self.zone_inner = getattr(self, "zone_inner", {})
            self.zone_inner[side] = zi
        mid = ttk.Frame(zones)
        mid.grid(row=0, column=1, padx=8)
        ttk.Button(mid, text="⇄", width=3, command=self.swap).pack()

        opt = ttk.Frame(self, padding=(10, 4))
        opt.pack(fill="x")
        ttk.Label(opt, text=T("Hledat soubor:")).pack(side="left")
        ttk.Combobox(opt, textvariable=self.v_layout, values=list(LAYOUT_MODES.values()), state="readonly",
                     width=40).pack(side="left", padx=4)
        ttk.Label(opt, text=T("Shoda:")).pack(side="left", padx=(8, 0))
        ttk.Combobox(opt, textvariable=self.v_match, values=list(MATCH_MODES.values()), state="readonly",
                     width=22).pack(side="left", padx=4)
        ttk.Checkbutton(opt, text=T("skryté soubory"), variable=self.v_hidden).pack(side="left", padx=6)
        self.btn = ttk.Button(opt, text=T("Porovnat"), command=self.start_compare)
        ttk.Button(opt, text=T("🔓 Opravit práva…"),
                   command=lambda: PermsDialog(self.root, self.paths["B"] or self.paths["A"])).pack(side="right", padx=6)
        self.btn.pack(side="right")

        prog = ttk.Frame(self, padding=(10, 2))
        prog.pack(fill="x")
        self.pbar = ttk.Progressbar(prog, mode="determinate", maximum=1.0)
        self.pbar.pack(fill="x")
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        self._bold = bold
        self.lbl_sum = ttk.Label(prog, text="", font=bold)
        self.lbl_sum.pack(fill="x", pady=(2, 0))

        flt = ttk.Frame(self, padding=(10, 4, 10, 0))
        flt.pack(fill="x")
        ttk.Label(flt, text=T("Zobrazit:")).pack(side="left")
        cb = ttk.Combobox(flt, textvariable=self.v_view, values=list(VIEWS), state="readonly", width=30)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self.render())
        ttk.Button(flt, text=T("Zaškrtnout vše zobrazené"), command=lambda: self.set_include(True)).pack(side="right")
        ttk.Button(flt, text=T("Odškrtnout vše zobrazené"),
                   command=lambda: self.set_include(False)).pack(side="right", padx=4)

        outer = ttk.Frame(self, padding=(10, 4))
        outer.pack(fill="both", expand=True)
        cols = ("inc", "status", "rel", "sa", "da", "sb", "db")
        self.col_labels, self.sort_col, self.sort_desc = {}, None, False
        tf, self.tree = framed_tree(outer, self.colors, columns=cols, show="headings", selectmode="extended")
        tf.pack(fill="both", expand=True)
        for c, t, w, a, st in (("inc", T("Doplnit"), 60, "center", False), ("status", T("Stav"), 110, "w", False),
                               ("rel", T("Cesta"), 420, "w", True), ("sa", T("Velikost A"), 120, "e", False),
                               ("da", T("Změněno A"), 120, "w", False), ("sb", T("Velikost B"), 120, "e", False),
                               ("db", T("Změněno B"), 120, "w", False)):
            self.tree.heading(c, text=t, anchor=a if a != "center" else "center",
                              command=lambda c=c: self.set_sort(c))
            self.tree.column(c, width=w, anchor=a, stretch=st)
            self.col_labels[c] = t
        self.tree.tag_configure("onlyA", foreground="#0b57d0")
        self.tree.tag_configure("onlyB", foreground="#7b1fa2")
        self.tree.tag_configure("diff", foreground="#b3261e")
        self.tree.tag_configure("type", foreground="#b3261e")
        self.tree.tag_configure("same", foreground="#2e7d32")
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<space>", lambda e: (self.toggle_selected(), "break")[1])
        self.tree.bind("<Double-1>", lambda e: self.reveal("A" if self._sel_has("A") else "B"))
        for b in ("<Button-2>", "<Button-3>", "<Control-Button-1>"):
            self.tree.bind(b, self.on_context)
        self.ctx = tk.Menu(self, tearoff=False)
        self.ctx.add_command(label=T("Zobrazit v A ve Finderu"), command=lambda: self.reveal("A"))
        self.ctx.add_command(label=T("Zobrazit v B ve Finderu"), command=lambda: self.reveal("B"))
        self.ctx.add_command(label=T("Rychlý náhled A"), command=lambda: self.quicklook("A"))
        self.ctx.add_command(label=T("Rychlý náhled B"), command=lambda: self.quicklook("B"))
        self.ctx.add_separator()
        self.ctx.add_command(label=T("Zaškrtnout / odškrtnout"), command=self.toggle_selected)

        bot = ttk.Frame(self, padding=(10, 4, 10, 10))
        bot.pack(fill="x")
        ttk.Combobox(bot, textvariable=self.v_dir, values=list(DIRECTIONS.values()), state="readonly",
                     width=48).pack(side="left")
        pc = ttk.Combobox(bot, textvariable=self.v_policy, values=list(CONFLICT_POLICIES.values()),
                          state="readonly", width=56)
        pc.pack(side="left", padx=6)
        pc.bind("<<ComboboxSelected>>", lambda e: self.on_policy())
        ttk.Checkbutton(bot, text=T("ověřit kopie bajt po bajtu"), variable=self.v_verify).pack(side="left")
        ttk.Button(bot, text=T("Export CSV…"), command=self.export).pack(side="right")
        ttk.Button(bot, text=T("Doplnit"), command=self.do_sync).pack(side="right", padx=6)

    def setup_dnd(self):
        for side in ("A", "B"):
            for w in (self.zone[side], self.zone_inner[side], self.zone_lbl[side], self.zone_path[side]):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", lambda e, s=side: self.on_drop(e, s))
        for w in (self, self.tree):          # puštění jinam na kartu: 1 složka → prázdné místo, 2 → A i B
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", lambda e: self.on_drop(e, None))

    def on_drop(self, event, side):
        self.on_paths(list(self.root.tk.splitlist(event.data)), side)
        return event.action

    def on_paths(self, paths, side=None):
        if self.busy:
            self.v_status.set(T("Počkej, až doběhne porovnání nebo kopírování."))
            return
        self.cmp_params = None
        dirs = [p for p in (os.path.abspath(x) for x in paths) if os.path.isdir(p)]
        if not dirs:
            self.v_status.set(T("Přetáhni složku nebo disk (ne soubor)."))
            return
        if len(dirs) >= 2:
            self.paths["A"], self.paths["B"] = dirs[0], dirs[1]
        elif side:
            self.paths[side] = dirs[0]
        else:
            self.paths["B" if self.paths["A"] and not self.paths["B"] else "A"] = dirs[0]
        self.items = []
        self.render()
        self._update_zone_labels()
        if self.paths["A"] and self.paths["B"] and not self.busy:
            self.start_compare()

    def choose(self, side):
        d = filedialog.askdirectory(title=T("Vyber místo {0}", side))
        if d:
            self.on_paths([d], side)

    def swap(self):
        if self.busy:
            self.root.bell()
            return
        self.paths["A"], self.paths["B"] = self.paths["B"], self.paths["A"]
        self.items, self.cmp_params = [], None       # staré výsledky už neplatí
        self.render()
        self._update_zone_labels()
        if self.items and not self.busy:
            self.start_compare()

    def _update_zone_labels(self):
        for side in ("A", "B"):
            p = self.paths[side]
            self.zone_path[side].configure(text=("Macintosh HD" if p == "/" else p) or T("(nevybráno)"))

    def settings(self):
        return {"cmp_a": self.paths["A"], "cmp_b": self.paths["B"],
                "cmp_layout": _inv(LAYOUT_MODES).get(self.v_layout.get()),
                "cmp_match": _inv(MATCH_MODES).get(self.v_match.get()),
                "cmp_hidden": self.v_hidden.get(), "cmp_dir": _inv(DIRECTIONS).get(self.v_dir.get()),
                "cmp_verify": self.v_verify.get()}

    # ----------------------------------------------------------------- porovnání
    def check_paths(self):
        a, b = self.paths["A"], self.paths["B"]
        if not a or not b:
            self.v_status.set(T("Vyber obě místa – A i B."))
            return False
        if not os.path.isdir(a) or not os.path.isdir(b):
            messagebox.showerror(APP_TITLE, T("Jedno z míst neexistuje (odpojený disk?)."))
            return False
        if a == b or in_folder(a, b) or in_folder(b, a) or paths_overlap(a, b):
            messagebox.showerror(APP_TITLE, T("Místa A a B nesmí být stejná ani jedno uvnitř druhého."))
            return False
        return True

    def start_compare(self):
        if self.busy:
            self.cancel.set()
            return
        if not self.check_paths():
            return
        layout = _inv(LAYOUT_MODES)[self.v_layout.get()]
        match = _inv(MATCH_MODES)[self.v_match.get()]
        self.pending_params = (self.paths["A"], self.paths["B"], layout, match)
        self.set_busy(True, T("Zastavit"))
        threading.Thread(target=self.worker_compare,
                         args=(self.paths["A"], self.paths["B"], layout, match, self.v_hidden.get()),
                         daemon=True).start()

    def worker_compare(self, a, b, layout, match, hidden, after_sync=None):
        prog = lambda text, frac, path: self.q.put(("progress", text, frac))
        t0 = time.monotonic()
        try:
            A, ea = scan_tree(a, hidden, self.cancel, prog, "A")
            B, eb = scan_tree(b, hidden, self.cancel, prog, "B")
            prog(T("Porovnávám…"), None, None)
            items = compare_trees(A, B, layout, match, self.cancel, prog)
            self.q.put(("compared", items, ea + eb, time.monotonic() - t0, after_sync))
        except Cancelled:
            self.q.put(("cancelled",))
        except Exception as exc:
            self.q.put(("error", f"{type(exc).__name__}: {exc}"))

    def set_busy(self, busy, text=None):
        self.busy = busy
        self.cancel.clear()
        self.btn.configure(text=(text or T("Porovnat")) if busy else T("Porovnat"))
        if busy:
            self.pbar.configure(mode="indeterminate")
            self.pbar.start(12)
        else:
            self.pbar.stop()
            self.pbar.configure(mode="determinate", value=0)

    def poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                try:
                    self.handle(msg)
                except Exception:
                    log_exception(*sys.exc_info(), where=T("porovnání"))
                    if msg[0] in ("compared", "cancelled", "error"):
                        self.set_busy(False)
                    self.v_status.set(T("Vnitřní chyba – zapsáno do ~/Library/Logs/DuplicitniSoubory/chyby.log"))
        except queue.Empty:
            pass
        finally:
            self.after(100, self.poll)

    def handle(self, msg):
        kind = msg[0]
        if kind == "progress":
            _, text, frac = msg
            self.v_status.set(text)
            if frac is not None:
                if str(self.pbar.cget("mode")) != "determinate":
                    self.pbar.stop()
                    self.pbar.configure(mode="determinate")
                self.pbar.configure(value=frac)
        elif kind == "compared":
            _, items, errs, secs, after_sync = msg
            self.set_busy(False)
            self.items = items
            self.cmp_params = getattr(self, "pending_params", None)
            if _inv(CONFLICT_POLICIES)[self.v_policy.get()] == "newer":
                self.on_policy(render=False)
            self.render()
            txt = T("Porovnáno za {0:.0f} s.", secs)
            if errs:
                txt += T("  Nepřístupné položky: {0} (Plný přístup k disku).", errs)
            self.v_status.set(txt)
            if after_sync:
                self.show_sync_result(*after_sync)
        elif kind == "synced":
            _, done, errors = msg
            self.v_status.set(T("Kopírování hotovo, porovnávám znovu…"))
            self.set_busy(True, T("Zastavit"))
            layout = _inv(LAYOUT_MODES)[self.v_layout.get()]
            match = _inv(MATCH_MODES)[self.v_match.get()]
            self.pending_params = (self.paths["A"], self.paths["B"], layout, match)
            threading.Thread(target=self.worker_compare,
                             args=(self.paths["A"], self.paths["B"], layout, match, self.v_hidden.get(),
                                   (done, errors)), daemon=True).start()
        elif kind == "cancelled":
            self.set_busy(False)
            self.v_status.set("Zastaveno.")
        elif kind == "error":
            self.set_busy(False)
            self.v_status.set(T("Chyba: ") + msg[1])
            messagebox.showerror(APP_TITLE, msg[1])

    def show_sync_result(self, done, errors):
        rest = sum(1 for it in self.items if it.status != "same")
        text = T("Doplněno {0} položek.", done)
        match = (self.cmp_params or ("", "", "", "quick"))[3]
        if rest:
            text += T(" Zbývá rozdílů: {0}.", rest)
        elif match == "content":
            text += T(" Obě místa mají nyní stejný obsah (porovnáno bajt po bajtu). ✅")
        else:
            text += (T(" Obě místa mají stejné soubory podle: {0}. Pro jistotu ještě porovnej se shodou „obsah“.", MATCH_MODES[match]))
        self.v_status.set(text + T("  Záznam: ~/Library/Logs/DuplicitniSoubory"))
        if errors:
            t = "\n".join(f"• {os.path.basename(p)}: {e}" for p, e in errors[:15])
            if len(errors) > 15:
                t += T("\n… a dalších {0}", len(errors) - 15)
            messagebox.showwarning(APP_TITLE, T("Některé položky se nepodařilo doplnit:\n\n{0}", t))
        else:
            messagebox.showinfo(APP_TITLE, text)

    # ----------------------------------------------------------------- výpis
    def summary(self):
        c = {k: [0, 0] for k in STATUS_LABEL}
        for it in self.items:
            e = it.a or it.b
            c[it.status][0] += e.count if e.kind == "d" else 1
            c[it.status][1] += e.size
        return c

    def render(self):
        self.tree.delete(*self.tree.get_children())
        self.iid_item.clear()
        if not self.items:
            self.lbl_sum.configure(text="")
            return
        c = self.summary()
        self.lbl_sum.configure(
            text=T("Jen v A: {0} ({1})   •   Jen v B: {2} ({3})   •   Liší se: {4}   •   Stejné: {5}", fmt_int(c['onlyA'][0]), fmt_size(c['onlyA'][1]), fmt_int(c['onlyB'][0]), fmt_size(c['onlyB'][1]), fmt_int(c['diff'][0] + c['type'][0]), fmt_int(c['same'][0])))
        want = VIEWS[self.v_view.get()]
        shown = [it for it in self.items if it.status in want]
        if self.sort_col:
            shown.sort(key=self._sort_key(self.sort_col), reverse=self.sort_desc)
        for i, it in enumerate(shown[:MAX_ROWS_SHOWN]):
            iid = f"c{i}"
            self.iid_item[iid] = it
            self.tree.insert("", "end", iid=iid, values=self._values(it), tags=(it.status,))
        if len(shown) > MAX_ROWS_SHOWN:
            self.tree.insert("", "end", values=("", "", T("… a dalších {0} položek (Doplnit pracuje se všemi)", fmt_int(len(shown) - MAX_ROWS_SHOWN)), "", "", "", ""))
        if not shown:
            self.tree.insert("", "end", values=("", "", T("Nic k zobrazení – v tomto pohledu nejsou žádné položky."),
                                                "", "", "", ""))

    def set_sort(self, col):
        if col == "inc":
            return
        if col == self.sort_col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col, self.sort_desc = col, col in ("sa", "da", "sb", "db")
        for c, label in self.col_labels.items():
            arrow = ("  ▼" if self.sort_desc else "  ▲") if c == self.sort_col else ""
            self.tree.heading(c, text=label + arrow)
        self.render()

    @staticmethod
    def _sort_key(col):
        order = {"onlyA": 0, "onlyB": 1, "diff": 2, "type": 3, "same": 4}

        def side(it, s):
            return it.a if s == "A" else it.b
        if col == "status":
            return lambda it: (order[it.status], it.rel.casefold())
        if col == "rel":
            return lambda it: it.rel.casefold()
        s = "A" if col in ("sa", "da") else "B"
        if col in ("sa", "sb"):
            return lambda it: (side(it, s).size if side(it, s) else -1)
        return lambda it: (side(it, s).mtime if side(it, s) and side(it, s).kind == "f" else 0)

    def _side_vals(self, e):
        if e is None:
            return "—", ""
        if e.kind == "d":
            return T("složka: {0} s., {1}", fmt_int(e.count), fmt_size(e.size)), ""
        if e.kind == "l":
            return T("odkaz"), ""
        return fmt_size(e.size), fmt_date(e.mtime)

    def _values(self, it):
        rel = it.rel
        if it.a and it.b and it.a.rel != it.b.rel:
            rel = f"{it.a.rel}   ⟷   {it.b.rel}"
        if it.note:
            rel += f"   ({it.note})"
        sa, da = self._side_vals(it.a)
        sb, db = self._side_vals(it.b)
        inc = "" if it.status in ("same", "type") else (CHECK_ON if it.include else CHECK_OFF)
        return (inc, STATUS_LABEL[it.status], rel, sa, da, sb, db)

    def refresh_row(self, iid):
        self.tree.item(iid, values=self._values(self.iid_item[iid]))

    def toggle(self, iid):
        it = self.iid_item.get(iid)
        if not it or it.status in ("same", "type"):
            return
        if it.status == "diff" and _inv(CONFLICT_POLICIES)[self.v_policy.get()] == "skip":
            self.v_status.set(T("Rozdílné verze se sjednotí jen s volbou „Novější verze vyhraje…“ dole."))
            self.root.bell()
            return
        it.include = not it.include
        self.refresh_row(iid)

    def toggle_selected(self):
        for iid in self.tree.selection():
            self.toggle(iid)

    def on_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "cell" and self.tree.identify_column(event.x) == "#1":
            iid = self.tree.identify_row(event.y)
            if iid in self.iid_item:
                self.toggle(iid)
                return "break"

    def set_include(self, val):
        newer = _inv(CONFLICT_POLICIES)[self.v_policy.get()] == "newer"
        for iid, it in self.iid_item.items():
            if it.status in ("onlyA", "onlyB") or (it.status == "diff" and newer):
                it.include = val
                self.refresh_row(iid)

    def on_policy(self, render=True):
        newer = _inv(CONFLICT_POLICIES)[self.v_policy.get()] == "newer"
        for it in self.items:
            if it.status == "diff":
                it.include = newer and it.a.kind == "f" and it.b.kind == "f"
        if render:
            self.render()

    def _sel_item(self):
        sel = self.tree.selection()
        return self.iid_item.get(sel[0]) if sel else None

    def _sel_has(self, side):
        it = self._sel_item()
        return bool(it and (it.a if side == "A" else it.b))

    def on_context(self, event):
        iid = self.tree.identify_row(event.y)
        if iid in self.iid_item:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            it = self.iid_item[iid]
            self.ctx.entryconfigure(0, state="normal" if it.a else "disabled")
            self.ctx.entryconfigure(1, state="normal" if it.b else "disabled")
            self.ctx.entryconfigure(2, state="normal" if it.a else "disabled")
            self.ctx.entryconfigure(3, state="normal" if it.b else "disabled")
            self.ctx.tk_popup(event.x_root, event.y_root)
        return "break"

    def reveal(self, side):
        it = self._sel_item()
        e = it and (it.a if side == "A" else it.b)
        if e:
            subprocess.run(["open", "-R", e.path])

    def quicklook(self, side):
        it = self._sel_item()
        e = it and (it.a if side == "A" else it.b)
        if e:
            subprocess.Popen(["qlmanage", "-p", e.path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ----------------------------------------------------------------- doplnění
    def do_sync(self):
        if self.busy or not self.items or not self.check_paths():
            if not self.items:
                self.v_status.set(T("Nejdřív porovnej obě místa."))
            return
        direction = _inv(DIRECTIONS)[self.v_dir.get()]
        policy = _inv(CONFLICT_POLICIES)[self.v_policy.get()]
        layout = _inv(LAYOUT_MODES)[self.v_layout.get()]
        if self.cmp_params != (self.paths["A"], self.paths["B"], layout, _inv(MATCH_MODES)[self.v_match.get()]):
            messagebox.showinfo(APP_TITLE, T("Místa nebo nastavení se od porovnání změnily – porovnej znovu."))
            return
        steps = sync_plan(self.items, direction, policy)
        if not steps:
            messagebox.showinfo(APP_TITLE, T("Není co doplnit (v tomto směru a se zaškrtnutými položkami)."))
            return
        to_a, to_b = plan_bytes(steps)
        n_a = sum(1 for k, it, d in steps if k == "copy" and d == "BtoA")
        n_b = sum(1 for k, it, d in steps if k == "copy" and d == "AtoB")
        n_new = sum(1 for k, it, d in steps if k == "newer")
        problems = []
        for side, need in (("A", to_a), ("B", to_b)):
            if need:
                free = shutil.disk_usage(self.paths[side]).free
                if need > free * 0.98:
                    problems.append(T("Na místě {0} chybí místo: potřeba {1}, volno {2}.", side, fmt_size(need), fmt_size(free)))
        if problems:
            messagebox.showerror(APP_TITLE, "\n".join(problems))
            return
        skipped_diff = sum(1 for it in self.items if it.status == "diff") - n_new
        lines = [T("Do B se zkopíruje: {0} položek", n_b) if n_b else "",
                 T("Do A se zkopíruje: {0} položek", n_a) if n_a else "",
                 T("Rozdílné verze sjednotit: {0} (starší se přejmenuje na „… (starší verze …)“)", n_new) if n_new else "",
                 T("Rozdílné verze ponechané beze změny: {0}", skipped_diff) if skipped_diff > 0 else "",
                 T("Celkem k zápisu: A {0}, B {1}", fmt_size(to_a), fmt_size(to_b))]
        msg = "\n".join(l for l in lines if l)
        if not messagebox.askyesno(APP_TITLE, T("Doplnit obsah?\n\n{0}\n\nNic se nesmaže ani nepřepíše – soubory se jen přidají.\n\nPokračovat?", msg)):
            return
        self.set_busy(True, T("Zastavit"))
        prog = lambda text, frac, path: self.q.put(("progress", text, frac))
        a, b, verify = self.paths["A"], self.paths["B"], self.v_verify.get()

        def work():
            try:
                done, errors = run_sync(steps, a, b, layout, direction, verify, self.cancel, prog)
            except Exception as exc:
                done, errors = 0, [("", str(exc))]
            self.q.put(("synced", done, errors))
        threading.Thread(target=work, daemon=True).start()

    def export(self):
        if not self.items:
            return
        path = filedialog.asksaveasfilename(title=T("Uložit porovnání"), defaultextension=".csv",
                                            initialfile="porovnani.csv", filetypes=[("CSV", "*.csv")])
        if path:
            try:
                export_compare_csv(self.items, self.paths["A"], self.paths["B"], path)
                self.v_status.set(T("Uloženo: {0}", path))
            except OSError as exc:
                messagebox.showerror(APP_TITLE, str(exc))


# ---------------- aktualizace z GitHubu ----------------

def version_tuple(v):
    """'v2.1.3' → (2, 1, 3); nečíselné části se ignorují."""
    out = []
    for part in str(v).strip().lstrip("vV").split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out + [0] * (3 - len(out)))


def _curl(args, timeout):
    """Systémový curl používá certifikáty macOS (Python z python.org je sám nemusí mít)."""
    return subprocess.run(["/usr/bin/curl", "-fsSL", "--max-time", str(timeout), *args],
                          capture_output=True, timeout=timeout + 5)


def fetch_latest_release():
    """Poslední vydání na GitHubu: {tag, url, notes, dmg_url, dmg_name, dmg_size} nebo None."""
    try:
        r = _curl(["-H", "Accept: application/vnd.github+json",
                   f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"], 10)
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout.decode("utf-8", "replace"))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if not isinstance(data, dict) or not data.get("tag_name"):
        return None
    dmg = next((a for a in data.get("assets", []) if str(a.get("name", "")).lower().endswith(".dmg")), None)
    return {"tag": data["tag_name"], "url": data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases"),
            "notes": data.get("body") or "", "dmg_url": dmg and dmg.get("browser_download_url"),
            "dmg_name": dmg and dmg.get("name"), "dmg_size": (dmg or {}).get("size", 0)}


def download_update(info):
    """Stáhne DMG do složky Stažené soubory (nikdy nic nepřepíše). Vrací cestu."""
    dest_dir = os.path.expanduser("~/Downloads")
    os.makedirs(dest_dir, exist_ok=True)
    name = os.path.basename(info["dmg_name"] or "DuplicateFiles.dmg")
    target = _unique(os.path.join(dest_dir, name))
    tmp = target + ".download"
    r = _curl(["-o", tmp, info["dmg_url"]], 900)
    if r.returncode != 0 or not os.path.exists(tmp):
        if os.path.exists(tmp):
            os.remove(tmp)
        raise OSError(r.stderr.decode("utf-8", "replace").strip() or T("stahování selhalo"))
    if info.get("dmg_size") and os.path.getsize(tmp) != info["dmg_size"]:
        os.remove(tmp)
        raise OSError(T("stažený soubor nemá očekávanou velikost"))
    os.rename(tmp, target)
    return target


def app_bundle_path():
    """Cesta k DuplicateFiles.app, ze které aplikace běží (None při spuštění ze zdrojových kódů)."""
    if getattr(sys, "frozen", False):
        app = os.path.abspath(os.path.join(os.path.dirname(sys.executable), "..", ".."))
        if app.endswith(".app"):
            return app
    return None


def prepare_update(info):
    """Stáhne instalační skript i novou verzi (DMG) do dočasné složky, DOKUD aplikace ještě běží.
    Stahuje curl → soubor nedostane karanténu macOS. Vrací (složka, skript, dmg); při chybě OSError."""
    work = tempfile.mkdtemp(prefix="duplicate-files-update-")
    script, dmg = os.path.join(work, "install.sh"), os.path.join(work, "DuplicateFiles.dmg")
    r = _curl(["-o", script, INSTALL_URL], 30)
    if r.returncode != 0 or not os.path.getsize(script):
        shutil.rmtree(work, ignore_errors=True)
        raise OSError(T("instalační skript se nepodařilo stáhnout"))
    r = _curl(["-o", dmg, info["dmg_url"]], 900)
    if r.returncode != 0 or not os.path.exists(dmg):
        shutil.rmtree(work, ignore_errors=True)
        raise OSError(r.stderr.decode("utf-8", "replace").strip() or T("stahování selhalo"))
    if info.get("dmg_size") and os.path.getsize(dmg) != info["dmg_size"]:
        shutil.rmtree(work, ignore_errors=True)
        raise OSError(T("stažený soubor nemá očekávanou velikost"))
    r = subprocess.run(["/usr/bin/hdiutil", "verify", "-quiet", dmg], capture_output=True) if IS_MAC else None
    if r is not None and r.returncode != 0:
        shutil.rmtree(work, ignore_errors=True)
        raise OSError(T("stažený soubor je poškozený"))
    return work, script, dmg


def install_update(root, script=None, dmg=None):
    """Spustí instalaci na pozadí: počká, až se aplikace ukončí, nainstaluje novou verzi na stejné
    místo a spustí ji. Když instalace selže, spustí se zase stará verze."""
    app = app_bundle_path()
    env = f"WAIT_PID={os.getpid()}"
    if app:
        env += f" INSTALL_DIR={_shq(os.path.dirname(app))}"
    if dmg:
        env += f" DMG_FILE={_shq(dmg)}"
    os.makedirs(LOG_DIR, exist_ok=True)
    log = os.path.join(LOG_DIR, "aktualizace.log")
    if script:
        cmd = f"{env} /bin/bash {_shq(script)} >> {_shq(log)} 2>&1; rm -rf {_shq(os.path.dirname(script))}"
    else:
        cmd = f"/usr/bin/curl -fsSL {_shq(INSTALL_URL)} | {env} /bin/bash >> {_shq(log)} 2>&1"
    subprocess.Popen(["/bin/bash", "-c", cmd], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    root.destroy()


def restart_app(root):
    """Spustí aplikaci znovu (kvůli změně jazyka)."""
    exe = sys.executable
    if getattr(sys, "frozen", False):
        app = os.path.abspath(os.path.join(os.path.dirname(exe), "..", ".."))
        if app.endswith(".app"):
            subprocess.Popen(["/bin/sh", "-c", f"sleep 1; open -n {_shq(app)}"])
            root.destroy()
            return
        subprocess.Popen(["/bin/sh", "-c", f"sleep 1; {_shq(exe)}"])
    else:
        subprocess.Popen([exe] + sys.argv)
    root.destroy()


def log_exception(exc_type, exc, tb, where=""):
    """Každou nečekanou chybu zapsat do ~/Library/Logs/DuplicitniSoubory/chyby.log."""
    import traceback
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "chyby.log"), "a", encoding="utf-8") as fh:
            fh.write(f"--- {datetime.datetime.now().isoformat(timespec='seconds')} {APP_VERSION} {where}\n{text}\n")
    except OSError:
        pass
    if sys.stderr is not None:
        sys.stderr.write(text)
    return text


def main():
    sys.excepthook = lambda t, e, tb: log_exception(t, e, tb, T("hlavní"))
    threading.excepthook = lambda a: log_exception(a.exc_type, a.exc_value, a.exc_traceback, T("vlákno"))
    root = tk.Tk()
    if tk.TkVersion < 8.6:
        messagebox.showwarning(APP_TITLE, T("Aplikace je sestavená se zastaralou knihovnou Tk {0} (systémový Python od Applu) – okno se nemusí správně vykreslit.\n\nNainstaluj Python z python.org a aplikaci sestav znovu.", tk.TkVersion))

    def on_tk_error(t, e, tb):
        log_exception(t, e, tb, "okno")
        try:
            messagebox.showerror(APP_TITLE, T("Vnitřní chyba: {0}\n\nPodrobnosti jsou v ~/Library/Logs/DuplicitniSoubory/chyby.log", e))
        except tk.TclError:
            pass
    root.report_callback_exception = on_tk_error
    try:
        app = App(root)
    except Exception:
        text = log_exception(*sys.exc_info(), where="start")
        messagebox.showerror(APP_TITLE, T("Aplikaci se nepodařilo spustit:\n\n") + text[-1500:]
                             + T("\n\nZáznam: ~/Library/Logs/DuplicitniSoubory/chyby.log"))
        root.destroy()
        return
    for p in sys.argv[1:]:          # spuštění s cestou (z Terminálu)
        if os.path.isdir(p):
            root.after(500, lambda p=p: app.set_roots([p]))
    root.mainloop()


if __name__ == "__main__":
    main()
