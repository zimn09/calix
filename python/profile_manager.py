"""Local profile slots: up to three independent local players.

Every slot is a separate SQLite database stored in the app's data folder, so a
profile owns its own skill progress, records, workouts, schedule, history, XP
and settings. Nothing is uploaded anywhere: switching profiles only opens a
different local file.

Slot 1 keeps using the original ``progress.db`` (so an existing installation
keeps its data without any migration). Slots 2 and 3 use ``profile-2.db`` and
``profile-3.db`` next to it, and the last used slot is remembered in
``active_profile.json``.
"""
import json
import os
import sqlite3
from pathlib import Path

from database import default_db_path

MAX_PROFILES = 3
ACTIVE_FILE = "active_profile.json"
SETTINGS_FILE = "settings.db"
UNLOCKS_FILE = "unlocks.db"


def data_root():
    """Folder that holds the database(s), audio cache and the profile index."""
    return default_db_path().parent


def _valid(slot):
    try:
        slot = int(slot)
    except (TypeError, ValueError):
        return False
    return 1 <= slot <= MAX_PROFILES


def slot_path(slot):
    """Path of the SQLite file that belongs to a profile slot (1-3)."""
    if not _valid(slot):
        raise ValueError(f"profile slot must be 1-{MAX_PROFILES}, got {slot!r}")
    slot = int(slot)
    if slot == 1:                       # backwards compatible: the original database
        return default_db_path()
    return data_root() / f"profile-{slot}.db"


def slot_exists(slot):
    return _valid(slot) and slot_path(slot).exists()


def _active_path():
    return data_root() / ACTIVE_FILE


def get_active_slot():
    """The last used profile slot (1 when the index is missing or corrupt)."""
    try:
        data = json.loads(_active_path().read_text(encoding="utf-8"))
        slot = int(data.get("active", 1))
    except (OSError, ValueError, TypeError, AttributeError):
        return 1
    return slot if _valid(slot) else 1


def set_active_slot(slot):
    if not _valid(slot):
        raise ValueError(f"profile slot must be 1-{MAX_PROFILES}, got {slot!r}")
    path = _active_path()
    path.write_text(json.dumps({"active": int(slot)}, indent=2) + "\n", encoding="utf-8")
    return int(slot)


def resolve_slot(explicit=None):
    """Pick the slot to open: explicit argument > CALIX_PROFILE > last used > 1."""
    for candidate in (explicit, os.environ.get("CALIX_PROFILE")):
        if candidate is None:
            continue
        try:
            slot = int(candidate)
        except (TypeError, ValueError):
            continue
        if _valid(slot):
            return slot
    return get_active_slot()


def read_slot(slot):
    """Read a slot's identity without touching the app's own connection.

    Returns ``{"name", "avatar", "accent", "level", "xp"}`` or None when the
    slot has no profile yet (missing file, empty database or an unfinished
    welcome screen). Works with older databases that have no XP tables yet.
    """
    if not slot_exists(slot):
        return None
    path = slot_path(slot)
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
    return {"name": row[0], "avatar": row[1], "accent": row[2] or "#4dabf7",
            "level": level, "xp": xp}


def slot_info(slot):
    """Everything the profile picker needs about one slot."""
    if not _valid(slot):
        raise ValueError(f"profile slot must be 1-{MAX_PROFILES}, got {slot!r}")
    slot = int(slot)
    identity = read_slot(slot)
    return {
        "slot": slot,
        "path": slot_path(slot),
        "exists": slot_exists(slot),
        "name": identity["name"] if identity else "",
        "avatar": identity["avatar"] if identity else "",
        "accent": identity["accent"] if identity else "#4dabf7",
        "level": identity["level"] if identity else 0,
        "xp": identity["xp"] if identity else 0,
        "active": slot == get_active_slot(),
    }


def slots():
    """All three slots, in order."""
    return [slot_info(i) for i in range(1, MAX_PROFILES + 1)]


def delete_slot(slot):
    """Delete one profile's local database (and its migration backups).

    The caller is responsible for moving the app to another slot first when this
    is the profile that is currently open.
    """
    if not _valid(slot):
        raise ValueError(f"profile slot must be 1-{MAX_PROFILES}, got {slot!r}")
    path = slot_path(slot)
    removed = False
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        try:
            candidate.unlink()
            removed = True
        except FileNotFoundError:
            pass
    for backup in path.parent.glob(path.name + ".bak-v*"):
        try:
            backup.unlink()
            removed = True
        except FileNotFoundError:
            pass
    return removed


def next_slot_after_delete(deleted):
    """Slot to open after deleting ``deleted``: another profile, else slot 1."""
    for slot in range(1, MAX_PROFILES + 1):
        if slot != deleted and read_slot(slot) is not None:
            return slot
    return 1


# ------------------------------------------------------------------- settings
def settings_path():
    """App-wide settings live outside the profile databases.

    The look, sound and accessibility options are a property of the app, not of
    a player, so they survive switching profiles. Every profile still keeps its
    own progress, workouts and history.
    """
    return data_root() / SETTINGS_FILE


def open_settings_db():
    """Open (and create on first run) the shared settings database."""
    con = sqlite3.connect(str(settings_path()))
    con.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    con.commit()
    return con


# --------------------------------------------------------------- avatar unlocks
def unlocks_path():
    """Avatars unlocked on any profile are remembered in this shared file."""
    return data_root() / UNLOCKS_FILE


def open_unlocks_db():
    """Open (and create on first run) the shared avatar-unlock database."""
    con = sqlite3.connect(str(unlocks_path()))
    con.execute("CREATE TABLE IF NOT EXISTS avatar_unlocks("
                "avatar_id TEXT PRIMARY KEY, unlocked TEXT NOT NULL, source TEXT NOT NULL DEFAULT '')")
    con.commit()
    return con
