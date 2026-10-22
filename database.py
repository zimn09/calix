"""Local SQLite storage: skill progress, records and schema migrations."""
import datetime as dt
import os
import shutil
import sqlite3
from pathlib import Path

VALID_STATUS = ("training", "completed")


def default_db_path():
    base = Path(os.environ.get("SKILLTREE_DATA") or Path.home() / ".calisthenics_skill_tree")
    base.mkdir(parents=True, exist_ok=True)
    return base / "progress.db"


def fetch_all(db, sql, params=()):
    """Run a query and return a list of dicts."""
    cur = db.execute(sql, params)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_one(db, sql, params=()):
    rows = fetch_all(db, sql, params)
    return rows[0] if rows else None


# ------------------------------------------------------------------ migrations
# PRAGMA user_version tracks the schema version. Databases created by the first
# release (skill tree only) have user_version 0 and already contain the v1
# tables, so migration 1 is idempotent and keeps all existing data.
def _m1_skill_tree(db):
    db.execute("""CREATE TABLE IF NOT EXISTS progress(
        skill_id TEXT PRIMARY KEY, status TEXT NOT NULL, updated TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS records(
        id INTEGER PRIMARY KEY AUTOINCREMENT, skill_id TEXT NOT NULL,
        value REAL NOT NULL, logged TEXT NOT NULL)""")


def _m2_training(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS exercises(
        id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
        difficulty INTEGER NOT NULL, kind TEXT NOT NULL,
        default_sets INTEGER NOT NULL, default_amount INTEGER NOT NULL,
        default_rest INTEGER NOT NULL, instructions TEXT NOT NULL DEFAULT '',
        skill_id TEXT, builtin INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS workouts(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '', style TEXT NOT NULL DEFAULT 'strength',
        created TEXT NOT NULL, updated TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS workout_exercises(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
        position INTEGER NOT NULL, exercise_id TEXT NOT NULL,
        sets INTEGER NOT NULL, reps INTEGER NOT NULL DEFAULT 0,
        hold_sec INTEGER NOT NULL DEFAULT 0, rest_sets INTEGER NOT NULL DEFAULT 60,
        rest_after INTEGER NOT NULL DEFAULT 90, note TEXT NOT NULL DEFAULT '');
    CREATE TABLE IF NOT EXISTS schedule_entries(
        id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
        weekday INTEGER, on_date TEXT,
        workout_id INTEGER REFERENCES workouts(id) ON DELETE CASCADE,
        is_rest INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
        created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS schedule_skips(
        entry_id INTEGER NOT NULL REFERENCES schedule_entries(id) ON DELETE CASCADE,
        on_date TEXT NOT NULL, PRIMARY KEY(entry_id, on_date));
    CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_id INTEGER REFERENCES workouts(id) ON DELETE SET NULL,
        workout_name TEXT NOT NULL, session_date TEXT NOT NULL, started TEXT NOT NULL,
        ended TEXT, status TEXT NOT NULL, elapsed_sec INTEGER NOT NULL DEFAULT 0,
        state_json TEXT NOT NULL DEFAULT '{}', entry_id INTEGER);
    CREATE TABLE IF NOT EXISTS session_sets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        ex_pos INTEGER NOT NULL, set_idx INTEGER NOT NULL,
        exercise_id TEXT NOT NULL, exercise_name TEXT NOT NULL, kind TEXT NOT NULL,
        target_reps INTEGER NOT NULL DEFAULT 0, target_hold INTEGER NOT NULL DEFAULT 0,
        reps INTEGER NOT NULL DEFAULT 0, hold INTEGER NOT NULL DEFAULT 0,
        rest_sec INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
        done INTEGER NOT NULL DEFAULT 0, done_at TEXT);
    CREATE INDEX IF NOT EXISTS idx_we_workout ON workout_exercises(workout_id, position);
    CREATE INDEX IF NOT EXISTS idx_ss_session ON session_sets(session_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(session_date, status);
    """)


def _m3_ranks_settings(db):
    """Settings, rank performances and a 'confirmed' flag on workout sets (existing data is untouched)."""
    db.executescript("""
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS performances(
        id INTEGER PRIMARY KEY AUTOINCREMENT, exercise_id TEXT NOT NULL, value REAL NOT NULL,
        logged TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
        session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE, note TEXT NOT NULL DEFAULT '');
    CREATE INDEX IF NOT EXISTS idx_perf_ex ON performances(exercise_id, logged);
    """)
    cols = [r[1] for r in db.execute("PRAGMA table_info(session_sets)")]
    if "confirmed" not in cols:
        db.execute("ALTER TABLE session_sets ADD COLUMN confirmed INTEGER NOT NULL DEFAULT 0")


def _m4_xp_achievements(db):
    """XP ledger, cached level state and achievement progress (all existing data is untouched)."""
    db.executescript("""
    CREATE TABLE IF NOT EXISTS xp_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL UNIQUE,             -- idempotency key: one reward per real achievement
        amount INTEGER NOT NULL, reason TEXT NOT NULL, category TEXT NOT NULL,
        earned_on TEXT NOT NULL,              -- date of the real activity
        awarded TEXT NOT NULL);               -- when it was credited
    CREATE TABLE IF NOT EXISTS xp_state(
        id INTEGER PRIMARY KEY CHECK (id = 1), total_xp INTEGER NOT NULL, level INTEGER NOT NULL,
        title TEXT NOT NULL, updated TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS achievements(
        id TEXT PRIMARY KEY, progress REAL NOT NULL DEFAULT 0, unlocked TEXT);
    CREATE INDEX IF NOT EXISTS idx_xp_earned ON xp_events(earned_on, id);
    """)


def _m5_library_profile(db):
    """Exercise library details, local profile, favourites and cosmetic unlocks.

    Everything is additive: no existing table or row is touched, so all
    progress, records, workouts, sessions and XP data survive the upgrade.
    """
    db.executescript("""
    CREATE TABLE IF NOT EXISTS exercise_details(
        exercise_id TEXT PRIMARY KEY REFERENCES exercises(id) ON DELETE CASCADE,
        muscles TEXT NOT NULL DEFAULT '',        -- comma separated muscle groups
        technique TEXT NOT NULL DEFAULT '',      -- step by step instructions
        mistakes TEXT NOT NULL DEFAULT '',       -- common mistakes
        tips TEXT NOT NULL DEFAULT '',           -- training tips
        easier TEXT NOT NULL DEFAULT '',         -- easier progressions
        harder TEXT NOT NULL DEFAULT '',         -- harder progressions
        prerequisites TEXT NOT NULL DEFAULT '',  -- required skills
        related TEXT NOT NULL DEFAULT '',        -- related exercise ids
        category TEXT NOT NULL DEFAULT '',
        difficulty INTEGER NOT NULL DEFAULT 1,
        equipment TEXT NOT NULL DEFAULT '',
        updated TEXT NOT NULL DEFAULT '');
    CREATE TABLE IF NOT EXISTS profiles(
        id INTEGER PRIMARY KEY CHECK (id = 1),
        name TEXT NOT NULL,
        avatar TEXT NOT NULL DEFAULT 'warrior',
        accent TEXT NOT NULL DEFAULT '#4dabf7',
        aura TEXT NOT NULL DEFAULT '',
        frame TEXT NOT NULL DEFAULT '',
        outfit TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        created TEXT NOT NULL,
        updated TEXT NOT NULL,
        welcome_seen INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS favorites(
        profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        exercise_id TEXT NOT NULL,
        created TEXT NOT NULL,
        PRIMARY KEY(profile_id, exercise_id));
    CREATE TABLE IF NOT EXISTS profile_cosmetics(
        profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        cosmetic_id TEXT NOT NULL,
        unlocked TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(profile_id, cosmetic_id));
    CREATE INDEX IF NOT EXISTS idx_fav_profile ON favorites(profile_id);
    """)
    # A profile may already exist without some columns on very old files.
    cols = [r[1] for r in db.execute("PRAGMA table_info(profiles)")]
    for name, default in (("accent", "'#4dabf7'"), ("welcome_seen", "0"),
                          ("aura", "''"), ("frame", "''"), ("outfit", "''"), ("title", "''")):
        if name not in cols:
            db.execute(f"ALTER TABLE profiles ADD COLUMN {name} "
                       f"{'TEXT NOT NULL DEFAULT' if default.startswith(chr(39)) else 'INTEGER NOT NULL DEFAULT'} "
                       f"{default}")
    # The key of the movement animation is stored with the exercise.
    ex_cols = [r[1] for r in db.execute("PRAGMA table_info(exercises)")]
    if "anim" not in ex_cols:
        db.execute("ALTER TABLE exercises ADD COLUMN anim TEXT NOT NULL DEFAULT ''")
    db.commit()

MIGRATIONS = [_m1_skill_tree, _m2_training, _m3_ranks_settings, _m4_xp_achievements, _m5_library_profile]
SCHEMA_VERSION = len(MIGRATIONS)


def migrate(db, path=None):
    current = db.execute("PRAGMA user_version").fetchone()[0]
    if current >= SCHEMA_VERSION:
        return
    # Back up an existing database before upgrading it.
    if path and Path(path).exists() and Path(path).stat().st_size > 0:
        db.commit()
        backup = Path(path).with_name(Path(path).name + f".bak-v{current}")
        if not backup.exists():
            shutil.copy2(str(path), str(backup))
    for i, step in enumerate(MIGRATIONS, start=1):
        if i > current:
            step(db)
            db.execute(f"PRAGMA user_version={i}")
            db.commit()


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_db_path()
        self.db = sqlite3.connect(str(self.path))
        self.db.execute("PRAGMA foreign_keys=ON")
        migrate(self.db, self.path)

    # ---------------------------------------------------------------- status
    def progress(self):
        return dict(self.db.execute("SELECT skill_id, status FROM progress"))

    def set_status(self, skill_id, status):
        """status: 'training', 'completed' or None (clears the skill)."""
        if status is None:
            self.db.execute("DELETE FROM progress WHERE skill_id=?", (skill_id,))
        elif status in VALID_STATUS:
            self.db.execute("INSERT OR REPLACE INTO progress VALUES(?,?,?)",
                            (skill_id, status, dt.datetime.now().isoformat(timespec="seconds")))
        self.db.commit()

    # --------------------------------------------------------------- records
    def add_record(self, skill_id, value):
        self.db.execute("INSERT INTO records(skill_id, value, logged) VALUES(?,?,?)",
                        (skill_id, float(value), dt.date.today().isoformat()))
        self.db.commit()

    def history(self, skill_id, limit=5):
        return self.db.execute(
            "SELECT value, logged FROM records WHERE skill_id=? ORDER BY id DESC LIMIT ?",
            (skill_id, limit)).fetchall()

    def best(self, skill_id):
        row = self.db.execute("SELECT MAX(value) FROM records WHERE skill_id=?", (skill_id,)).fetchone()
        return row[0] if row and row[0] is not None else None

    def bests(self):
        """{skill_id: (best_value, date_of_best)}"""
        out = {}
        for sid, val, day in self.db.execute(
                "SELECT skill_id, value, logged FROM records ORDER BY value ASC, id ASC"):
            out[sid] = (val, day)
        return out

    # ------------------------------------------------------------ bulk ops
    def reset(self):
        self.db.execute("DELETE FROM progress")
        self.db.execute("DELETE FROM records")
        self.db.commit()

    def export_data(self):
        return {
            "version": 1,
            "progress": self.progress(),
            "records": [{"skill": s, "value": v, "date": d} for s, v, d in
                        self.db.execute("SELECT skill_id, value, logged FROM records ORDER BY id")],
        }

    def import_data(self, data, known_ids):
        """Replace current data with an export. Unknown skill ids are skipped."""
        progress = {k: v for k, v in data.get("progress", {}).items()
                    if k in known_ids and v in VALID_STATUS}
        records = [r for r in data.get("records", []) if r.get("skill") in known_ids]
        self.reset()
        for k, v in progress.items():
            self.set_status(k, v)
        for r in records:
            self.db.execute("INSERT INTO records(skill_id, value, logged) VALUES(?,?,?)",
                            (r["skill"], float(r["value"]), str(r.get("date", dt.date.today().isoformat()))))
        self.db.commit()
        return len(progress)
