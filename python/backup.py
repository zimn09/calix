"""Local backups for CALIX.

Two kinds of archives are supported:

* **Full backup** - every local profile, the shared settings, avatar unlocks
  and the active-profile pointer. This is what *File -> Back up all data* uses.
* **Profile backup** - one profile database, so a single player can be moved
  to another computer or kept separately.

Everything is written with Python's standard library only and stays on this
computer. Live SQLite databases are snapshotted with SQLite's online backup API,
so a backup is safe to create while CALIX is running.
"""
import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import profile_manager as PM

FORMAT = "calix-backup"
VERSION = 1
APP_NAME = "CALIX 5.2"
MANIFEST = "calix-backup.json"
DB_FILES = ("progress.db", "profile-2.db", "profile-3.db", "settings.db", "unlocks.db")
JSON_FILES = ("active_profile.json",)
MANAGED = DB_FILES + JSON_FILES
MAX_BACKUPS = 20
MAX_UNCOMPRESSED = 512 * 1024 * 1024        # refuse absurdly large archives


# --------------------------------------------------------------------- helpers
def _now_name():
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _slot_file(slot):
    slot = int(slot)
    if not 1 <= slot <= PM.MAX_PROFILES:
        raise ValueError(f"profile slot must be 1-{PM.MAX_PROFILES}, got {slot!r}")
    return "progress.db" if slot == 1 else f"profile-{slot}.db"


def backups_dir(root=None):
    """Folder in which CALIX keeps its automatic safety backups."""
    folder = Path(root) if root is not None else PM.data_root()
    folder = folder / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def default_backup_path(root=None):
    return backups_dir(root) / f"calix-backup-{_now_name()}.zip"


def default_profile_path(slot, name="", root=None):
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", name or "profile").strip("-") or "profile"
    return backups_dir(root) / f"calix-profile-{slot}-{safe}-{_now_name()}.zip"


def _snapshot_db(src, dest):
    """Write a consistent copy of a live SQLite database to ``dest``."""
    src_con = sqlite3.connect(str(src), timeout=10)
    try:
        dest_con = sqlite3.connect(str(dest))
        try:
            src_con.backup(dest_con)
        finally:
            dest_con.close()
    finally:
        src_con.close()


def _read_profile(path):
    """Best-effort identity read from a profile snapshot (never raises)."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT name, avatar, accent FROM profiles WHERE id=1").fetchone()
            level, xp = 0, 0
            if row:
                try:
                    state = con.execute("SELECT level, total_xp FROM xp_state WHERE id=1").fetchone()
                except sqlite3.Error:
                    state = None
                if state:
                    level, xp = int(state[0]), int(state[1])
        finally:
            con.close()
    except sqlite3.Error:
        return None
    if not row or not row[0]:
        return None
    return {"name": row[0], "avatar": row[1] or "warrior",
            "accent": row[2] or "#4dabf7", "level": level, "xp": xp}


def _profile_entries(root, snapshots):
    """Manifest information about every profile found in the snapshot folder."""
    out = []
    for slot in range(1, PM.MAX_PROFILES + 1):
        name = _slot_file(slot)
        if name in snapshots:
            info = _read_profile(snapshots[name])
            out.append({
                "slot": slot,
                "file": name,
                "name": info["name"] if info else "",
                "level": info["level"] if info else 0,
                "xp": info["xp"] if info else 0,
            })
    return out


def _zip_folder(folder, dest):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(Path(folder).iterdir()):
            if path.is_file():
                zf.write(path, path.name)


def _cleanup(folder):
    if folder:
        shutil.rmtree(str(folder), ignore_errors=True)


# -------------------------------------------------------------------- creation
def create_full_backup(dest, root=None, note=""):
    """Back up every local profile plus the shared settings and unlocks.

    Returns ``(path, manifest)``. The destination may be a folder (a timestamped
    name is generated) or a ``.zip`` path.
    """
    root = Path(root) if root is not None else PM.data_root()
    dest = Path(dest)
    if dest.is_dir():
        dest = dest / f"calix-backup-{_now_name()}.zip"
    elif dest.suffix.lower() != ".zip":
        dest = dest.with_suffix(dest.suffix + ".zip")
    dest.parent.mkdir(parents=True, exist_ok=True)

    staging = Path(tempfile.mkdtemp(prefix="calix-backup-"))
    try:
        snapshots = {}
        for name in DB_FILES:
            src = root / name
            if not src.exists() or not src.stat().st_size:
                continue
            _snapshot_db(src, staging / name)
            snapshots[name] = str(staging / name)
        for name in JSON_FILES:
            src = root / name
            if src.exists():
                shutil.copy2(src, staging / name)

        if not snapshots:
            raise ValueError("There is no CALIX data to back up yet.")

        manifest = {
            "format": FORMAT,
            "version": VERSION,
            "kind": "all",
            "app": APP_NAME,
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "note": str(note or ""),
            "files": sorted(p.name for p in staging.iterdir()),
            "profiles": _profile_entries(root, snapshots),
        }
        (staging / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
        _zip_folder(staging, dest)
        return dest, manifest
    finally:
        _cleanup(staging)


def create_profile_backup(slot, dest, root=None):
    """Back up a single profile database. Returns ``(path, manifest)``."""
    slot = int(slot)
    name = _slot_file(slot)
    root = Path(root) if root is not None else PM.data_root()
    src = root / name
    if not src.exists() or not src.stat().st_size:
        raise ValueError(f"Profile {slot} has no local database to export.")
    dest = Path(dest)
    if dest.is_dir():
        info = _read_profile(src) or {}
        dest = default_profile_path(slot, info.get("name", ""), root)
    elif dest.suffix.lower() != ".zip":
        dest = dest.with_suffix(dest.suffix + ".zip")
    dest.parent.mkdir(parents=True, exist_ok=True)

    staging = Path(tempfile.mkdtemp(prefix="calix-profile-backup-"))
    try:
        _snapshot_db(src, staging / name)
        info = _read_profile(staging / name) or {}
        manifest = {
            "format": FORMAT,
            "version": VERSION,
            "kind": "profile",
            "app": APP_NAME,
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "slot": slot,
            "profile": {
                "name": info.get("name", ""),
                "avatar": info.get("avatar", "warrior"),
                "level": info.get("level", 0),
                "xp": info.get("xp", 0),
            },
            "files": [name],
        }
        (staging / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
        _zip_folder(staging, dest)
        return dest, manifest
    finally:
        _cleanup(staging)


def auto_backup(reason="automatic", root=None):
    """Create a timestamped safety backup in ``backups/`` and prune old ones."""
    folder = backups_dir(root)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", reason).strip("-") or "automatic"
    dest = folder / f"auto-{_now_name()}-{safe}.zip"
    path, _ = create_full_backup(dest, root, note=f"Automatic safety backup: {reason}")
    _prune(folder)
    return path


def _prune(folder):
    """Keep only the newest automatic backups; manual backups are never removed."""
    auto = sorted(folder.glob("auto-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in auto[MAX_BACKUPS:]:
        try:
            old.unlink()
        except OSError:
            pass


# ------------------------------------------------------------------ inspection
def inspect_backup(path):
    """Read and validate a backup manifest. Raises ``ValueError`` on bad files."""
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as zf:
            try:
                data = json.loads(zf.read(MANIFEST).decode("utf-8"))
            except KeyError as exc:
                raise ValueError("This ZIP is not a CALIX backup (manifest is missing).") from exc
            names = {i.filename for i in zf.infolist() if not i.is_dir()}
    except zipfile.BadZipFile as exc:
        raise ValueError("This file is not a valid ZIP archive.") from exc
    except OSError as exc:
        raise ValueError(f"Could not read the backup: {exc}") from exc

    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("This ZIP is not a CALIX backup.")
    if int(data.get("version", 0)) > VERSION:
        raise ValueError("This backup was created by a newer CALIX version.")
    kind = data.get("kind")
    if kind not in ("all", "profile"):
        raise ValueError("Unknown backup type.")
    files = data.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("The backup has no data files.")
    for name in files:
        if name not in MANAGED:
            raise ValueError(f"Unexpected file in backup: {name}")
        if name not in names:
            raise ValueError(f"The backup is incomplete: {name} is missing.")
    if kind == "profile":
        slot = int(data.get("slot", 0))
        expected = _slot_file(slot)
        if files != [expected] or expected not in names:
            raise ValueError("This profile backup is incomplete.")
    return data


def prepare_restore(path):
    """Validate an archive and extract its data to a private staging folder.

    Returns ``(staging_folder, manifest)``. Call :func:`restore_full` or
    :func:`restore_profile` afterwards and remove the staging folder.
    """
    manifest = inspect_backup(path)
    staging = Path(tempfile.mkdtemp(prefix="calix-restore-"))
    total = 0
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir() or info.filename not in MANAGED:
                    continue
                if info.file_size < 0 or (total := total + info.file_size) > MAX_UNCOMPRESSED:
                    raise ValueError("The backup is too large.")
                (staging / info.filename).write_bytes(zf.read(info))
            (staging / MANIFEST).write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        for name in manifest["files"]:
            extracted = staging / name
            if not extracted.exists():
                raise ValueError(f"The backup is incomplete: {name} is missing.")
            if name.endswith(".db"):
                _validate_db(extracted, name in ("progress.db", "profile-2.db", "profile-3.db"))
        if manifest.get("kind") == "profile":
            slot = int(manifest.get("slot", 0))
            if _slot_file(slot) not in manifest["files"]:
                raise ValueError("This profile backup is incomplete.")
        return staging, manifest
    except Exception:
        _cleanup(staging)
        raise


def _validate_db(path, profile):
    con = None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        result = con.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            raise ValueError("A database in the backup is damaged.")
        if profile:
            row = con.execute("SELECT name FROM sqlite_master "
                              "WHERE type='table' AND name='profiles'").fetchone()
            if not row:
                raise ValueError("A profile database in the backup is not valid.")
    except sqlite3.Error as exc:
        raise ValueError(f"A database in the backup cannot be opened: {exc}") from exc
    finally:
        if con is not None:
            con.close()


# ------------------------------------------------------------------- restoring
def _atomic_copy(src, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".restore-tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, target)


def _remove_sidecars(target):
    target = Path(target)
    for suffix in ("-wal", "-shm"):
        try:
            Path(str(target) + suffix).unlink()
        except FileNotFoundError:
            pass
    for backup in target.parent.glob(target.name + ".bak-v*"):
        try:
            backup.unlink()
        except OSError:
            pass


def restore_full(staging, root=None):
    """Replace all managed data files with the contents of a staged full backup."""
    staging = Path(staging)
    root = Path(root) if root is not None else PM.data_root()
    restored = []
    for name in MANAGED:
        src = staging / name
        target = root / name
        _remove_sidecars(target)
        if src.exists():
            _atomic_copy(src, target)
            restored.append(name)
        else:
            try:
                target.unlink()
            except FileNotFoundError:
                pass
    return restored


def restore_profile(staging, slot, root=None):
    """Replace one slot's database with a staged profile backup."""
    staging = Path(staging)
    root = Path(root) if root is not None else PM.data_root()
    name = _slot_file(slot)
    candidates = [p for p in staging.iterdir() if p.suffix == ".db"]
    if len(candidates) != 1:
        raise ValueError("This profile backup does not contain exactly one database.")
    target = root / name
    _remove_sidecars(target)
    _atomic_copy(candidates[0], target)
    return target


def discard_staging(staging):
    _cleanup(staging)
