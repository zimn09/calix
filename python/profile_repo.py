"""Local player profile: identity, favourites and cosmetic unlocks (no Qt).

Everything is stored in the same SQLite file as the rest of the app, so the
profile survives a restart and never leaves the machine. There is no login and
no online registration - just a local name, an avatar and some cosmetics.

The table is architected for several local profiles (a `profiles` table with an
id), but the app currently uses the single row with id 1.
"""
import datetime as dt

from avatar_data import AVATAR_BY_ID, COSMETIC_BY_ID, DEFAULT_AVATAR, DEFAULT_PALETTE
from database import fetch_all, fetch_one

PROFILE_ID = 1


def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


class ProfileRepo:
    """Read/write access to the local profile."""

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------ read
    def get(self):
        """The profile row or None when no profile was created yet."""
        return fetch_one(self.db, "SELECT * FROM profiles WHERE id=?", (PROFILE_ID,))

    def exists(self):
        return self.get() is not None

    def name(self):
        row = self.get()
        return row["name"] if row else ""

    def avatar(self):
        row = self.get()
        return row["avatar"] if row else DEFAULT_AVATAR

    def accent(self):
        row = self.get()
        return row["accent"] if row else DEFAULT_PALETTE

    # ----------------------------------------------------------------- write
    def create(self, name, avatar=DEFAULT_AVATAR, accent=DEFAULT_PALETTE):
        """Create (or overwrite) the profile. Returns the profile row."""
        name = (name or "").strip() or "Athlete"
        if avatar not in AVATAR_BY_ID:
            avatar = DEFAULT_AVATAR
        ts = _now()
        self.db.execute(
            """INSERT OR REPLACE INTO profiles(id,name,avatar,accent,created,updated,welcome_seen)
               VALUES(?,?,?,?,?,?,1)""",
            (PROFILE_ID, name, avatar, accent, ts, ts))
        self.db.commit()
        return self.get()

    def ensure(self, name="Athlete"):
        """Create a default profile when none exists (safety net)."""
        row = self.get()
        if row is None:
            row = self.create(name)
        return row

    def update(self, name=None, avatar=None, accent=None):
        """Change the identity. History, workouts and XP are never touched."""
        row = self.get()
        if row is None:
            row = self.create(name or "Athlete", avatar or DEFAULT_AVATAR, accent or DEFAULT_PALETTE)
            return row
        name = row["name"] if name is None else (name.strip() or row["name"])
        avatar = row["avatar"] if avatar is None else avatar
        accent = row["accent"] if accent is None else accent
        if avatar not in AVATAR_BY_ID:
            avatar = row["avatar"]
        self.db.execute("UPDATE profiles SET name=?,avatar=?,accent=?,updated=? WHERE id=?",
                        (name, avatar, accent, _now(), PROFILE_ID))
        self.db.commit()
        return self.get()

    def mark_welcome_seen(self):
        self.db.execute("UPDATE profiles SET welcome_seen=1, updated=? WHERE id=?", (_now(), PROFILE_ID))
        self.db.commit()

    def needs_welcome(self):
        row = self.get()
        return row is None or not row["welcome_seen"]

    # ----------------------------------------------------------- cosmetics
    def equipped(self):
        """{kind: cosmetic id} of the currently equipped cosmetics."""
        row = self.get()
        out = {}
        if row:
            for kind in ("aura", "frame", "outfit", "title"):
                cid = row[kind] if kind in row.keys() else ""
                if cid:
                    out[kind] = cid
        return out

    def equip(self, kind, cosmetic_id):
        """Equip a cosmetic of the given kind (empty id = remove)."""
        if kind not in ("aura", "frame", "outfit", "title"):
            return False
        if cosmetic_id and cosmetic_id not in self.unlocked_ids():
            return False
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(profiles)")}
        if kind not in cols:
            self.db.execute(f"ALTER TABLE profiles ADD COLUMN {kind} TEXT NOT NULL DEFAULT ''")
        self.db.execute(f"UPDATE profiles SET {kind}=?, updated=? WHERE id=?", (cosmetic_id or "", _now(), PROFILE_ID))
        self.db.commit()
        return True

    def unlocked_rows(self):
        return fetch_all(self.db, "SELECT * FROM profile_cosmetics WHERE profile_id=? ORDER BY unlocked",
                         (PROFILE_ID,))

    def unlocked_ids(self):
        return {r["cosmetic_id"] for r in self.unlocked_rows()}

    def unlock_cosmetic(self, cosmetic_id, source=""):
        """Unlock one cosmetic (idempotent). Returns True when it was new."""
        if cosmetic_id not in COSMETIC_BY_ID:
            return False
        cur = self.db.execute(
            "INSERT OR IGNORE INTO profile_cosmetics(profile_id,cosmetic_id,unlocked,source) VALUES(?,?,?,?)",
            (PROFILE_ID, cosmetic_id, _now(), source))
        self.db.commit()
        return bool(cur.rowcount)

    def sync_cosmetics(self, level=0, achievement_ids=()):
        """Unlock every cosmetic whose condition is now met.

        Returns the list of newly unlocked cosmetics so the UI can announce them.
        """
        have = self.unlocked_ids()
        won = set(achievement_ids)
        new = []
        for c in COSMETIC_BY_ID.values():
            if c["id"] in have:
                continue
            u = c["unlock"]
            ok = (u["type"] == "level" and level >= u["value"]) or \
                 (u["type"] == "achievement" and u["id"] in won)
            if ok and self.unlock_cosmetic(c["id"], u["type"] + ":" + str(u.get("value", u.get("id")))):
                new.append(c)
        return new

    # ---------------------------------------------------------- favourites
    def favorites(self):
        """Exercise ids marked as favourite, newest first."""
        return [r["exercise_id"] for r in
                fetch_all(self.db, "SELECT exercise_id FROM favorites WHERE profile_id=? "
                                   "ORDER BY created DESC", (PROFILE_ID,))]

    def is_favorite(self, ex_id):
        return bool(fetch_one(self.db, "SELECT 1 AS x FROM favorites "
                                       "WHERE profile_id=? AND exercise_id=?", (PROFILE_ID, ex_id)))

    def toggle_favorite(self, ex_id):
        """Flip the favourite flag. Returns the new state."""
        self.ensure()
        if self.is_favorite(ex_id):
            self.db.execute("DELETE FROM favorites WHERE profile_id=? AND exercise_id=?",
                            (PROFILE_ID, ex_id))
            state = False
        else:
            self.db.execute("INSERT OR IGNORE INTO favorites(profile_id,exercise_id,created) VALUES(?,?,?)",
                            (PROFILE_ID, ex_id, _now()))
            state = True
        self.db.commit()
        return state
