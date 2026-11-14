"""Cross-profile avatar unlocks kept in one shared local SQLite file.

Earning an avatar on any local profile unlocks it for every other profile, and
it stays unlocked even after that profile is deleted. Nothing is uploaded: the
file is ``unlocks.db`` next to the profile databases.
"""
import datetime as dt
import sqlite3
from pathlib import Path

from avatar_data import AVATAR_BY_ID, AVATARS, DEFAULT_AVATAR, unlocked_by_achievements


def ensure(db):
    """Create the unlock table in the shared database (idempotent)."""
    db.execute("CREATE TABLE IF NOT EXISTS avatar_unlocks("
               "avatar_id TEXT PRIMARY KEY, unlocked TEXT NOT NULL, source TEXT NOT NULL DEFAULT '')")
    db.commit()


def unlocked_ids(db):
    """Avatar ids available to every profile (free avatars are always included)."""
    ensure(db)
    ids = {r[0] for r in db.execute("SELECT avatar_id FROM avatar_unlocks")}
    ids.update(a["id"] for a in AVATARS if not a.get("unlock"))
    ids.add(DEFAULT_AVATAR)
    return ids


def unlock(db, avatar_ids, source=""):
    """Unlock avatars (idempotent). Returns the ones that were new."""
    ensure(db)
    new = []
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    for avatar_id in sorted(set(avatar_ids)):
        if avatar_id not in AVATAR_BY_ID:
            continue
        cur = db.execute(
            "INSERT OR IGNORE INTO avatar_unlocks(avatar_id,unlocked,source) VALUES(?,?,?)",
            (avatar_id, stamp, source))
        if cur.rowcount:
            new.append(AVATAR_BY_ID[avatar_id])
    db.commit()
    return new


def scan_profiles(db, paths):
    """Unlock everything earned by any local profile.

    * completed achievements in any slot unlock their avatars,
    * an avatar that was already equipped before the lock system existed is
      grandfathered in, so nobody loses their current look.
    """
    achievements = set()
    equipped = set()
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                achievements.update(r[0] for r in con.execute(
                    "SELECT id FROM achievements WHERE unlocked IS NOT NULL"))
                row = con.execute("SELECT avatar FROM profiles WHERE id=1").fetchone()
                if row and row[0]:
                    equipped.add(row[0])
            finally:
                con.close()
        except sqlite3.Error:
            continue

    new = {a["id"]: a for a in unlock(
        db, (aid for aid in equipped if AVATAR_BY_ID.get(aid, {}).get("unlock")), "existing profile")}
    for avatar in unlock(db, unlocked_by_achievements(achievements), "achievement"):
        new[avatar["id"]] = avatar
    return list(new.values())
