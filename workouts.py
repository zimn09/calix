"""Exercise library and custom workout CRUD (no Qt)."""
import datetime as dt
import uuid

from database import fetch_all, fetch_one
from exercise_details_data import DETAILS
from exercises_data import CATEGORY_ORDER, EXERCISES

STYLES = {
    "strength": ("Strength", dict(sets=5, reps=5, hold=10, rest_sets=120, rest_after=150)),
    "endurance": ("Endurance", dict(sets=3, reps=15, hold=30, rest_sets=45, rest_after=60)),
    "skill": ("Skill practice", dict(sets=6, reps=3, hold=10, rest_sets=90, rest_after=120)),
    "fullbody": ("Full body", dict(sets=3, reps=10, hold=20, rest_sets=60, rest_after=75)),
}
STYLE_COLORS = {"strength": "#ff6b6b", "endurance": "#4dabf7", "skill": "#b197fc", "fullbody": "#38d9a9"}

# (name, description, style, [(exercise_id, sets, reps-or-hold-seconds)])
EXAMPLE_WORKOUTS = [
    ("Push Day", "Chest, shoulders and triceps.", "strength",
     [("pushup", 4, 10), ("pike_pushup", 3, 8), ("dip", 3, 6), ("diamond_pushup", 3, 8)]),
    ("Pull Day", "Back and biceps.", "strength",
     [("pullup", 4, 6), ("australian_row", 3, 10), ("chinup", 3, 5), ("scap_pull", 3, 10), ("dead_hang", 3, 30)]),
    ("Legs & Core", "Lower body and trunk.", "endurance",
     [("squat", 4, 15), ("bulgarian", 3, 8), ("glute_bridge", 3, 15), ("calf_raise", 3, 15),
      ("hanging_knee_raise", 3, 10), ("hollow_hold", 3, 25), ("plank", 3, 40)]),
    ("Skill Training", "Low-fatigue practice of handstands, levers and planche.", "skill",
     [("wall_handstand", 5, 30), ("crow_pose", 4, 15), ("tuck_front_lever", 4, 8),
      ("planche_lean", 4, 15), ("skin_the_cat", 3, 4), ("tuck_l_sit", 4, 15)]),
]


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def entry_defaults(ex, style):
    """Starting sets/reps/hold/rest for an exercise, shaped by the training style."""
    s = STYLES.get(style, STYLES["strength"])[1]
    hard = ex["difficulty"] >= 2          # advanced moves keep their own conservative defaults
    if ex["kind"] == "hold":
        reps, hold = 0, (ex["default_amount"] if hard else s["hold"])
    else:
        reps, hold = (ex["default_amount"] if hard else s["reps"]), 0
    return dict(sets=ex["default_sets"] if hard else s["sets"], reps=reps, hold_sec=hold,
                rest_sets=max(ex["default_rest"], s["rest_sets"]) if style == "strength" else s["rest_sets"],
                rest_after=s["rest_after"])


def estimate_seconds(entries):
    """Rough workout length: ~3 s per rep, hold time, plus all rests."""
    total = 0
    for i, e in enumerate(entries):
        per = e["hold_sec"] if e.get("hold_sec") else e["reps"] * 3
        total += e["sets"] * max(per, 5) + max(0, e["sets"] - 1) * e["rest_sets"]
        if i < len(entries) - 1:
            total += e["rest_after"]
    return total


class WorkoutRepo:
    def __init__(self, db):
        self.db = db
        self.sync_builtin()

    # ------------------------------------------------------------ exercises
    def sync_builtin(self):
        for e in EXERCISES:
            self.db.execute(
                """INSERT OR REPLACE INTO exercises(id,name,category,difficulty,kind,default_sets,
                   default_amount,default_rest,instructions,skill_id,anim,builtin)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,1)""",
                (e["id"], e["name"], e["category"], e["difficulty"], e["kind"], e["default_sets"],
                 e["default_amount"], e["default_rest"], e["instructions"], e["skill_id"],
                 e.get("anim") or ""))
        self.db.commit()
        self.sync_details()

    def sync_details(self):
        """Copy the bundled detail data into the database (safe to call on every start)."""
        ts = now()
        for e in EXERCISES:
            d = DETAILS.get(e["id"])
            if d is None:
                continue
            self.db.execute(
                """INSERT OR REPLACE INTO exercise_details(exercise_id,muscles,technique,mistakes,tips,
                   easier,harder,prerequisites,related,category,difficulty,equipment,updated)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (e["id"], ", ".join(d.muscles), e["instructions"],
                 " | ".join(d.mistakes), " | ".join(d.tips),
                 ", ".join(d.easier), ", ".join(d.harder),
                 ", ".join(d.prereq), ", ".join(d.related),
                 e["category"], e["difficulty"], d.equipment, ts))
        self.db.commit()

    def details(self, ex_id):
        """Full detail row of one exercise (or None)."""
        return fetch_one(self.db, "SELECT * FROM exercise_details WHERE exercise_id=?", (ex_id,))

    def details_map(self):
        """{exercise_id: detail row} for the whole library."""
        return {r["exercise_id"]: r for r in
                fetch_all(self.db, "SELECT * FROM exercise_details")}

    def muscles(self):
        """All muscle groups used by the library, alphabetically."""
        out = set()
        for r in fetch_all(self.db, "SELECT muscles FROM exercise_details"):
            for m in (r["muscles"] or "").split(","):
                m = m.strip()
                if m:
                    out.add(m)
        return sorted(out)

    def exercises(self, category=None, difficulty=None, search="", muscle=None,
                  favorites=None, profile_id=1):
        """Library query with category / difficulty / free text / muscle filters.

        `favorites` is None (all), True (only favourites) or False (hide them).
        """
        sql, params = ("SELECT exercises.*, COALESCE(d.muscles,'') AS muscles, "
                       "COALESCE(d.equipment,'') AS equipment FROM exercises "
                       "LEFT JOIN exercise_details d ON d.exercise_id=exercises.id WHERE 1=1"), []
        if category:
            sql += " AND exercises.category=?"
            params.append(category)
        if difficulty is not None:
            sql += " AND exercises.difficulty=?"
            params.append(difficulty)
        if search.strip():
            q = f"%{search.strip().lower()}%"
            sql += (" AND (LOWER(exercises.name) LIKE ? OR LOWER(exercises.instructions) LIKE ? "
                    "OR LOWER(COALESCE(d.muscles,'')) LIKE ?)")
            params += [q, q, q]
        if muscle:
            sql += " AND LOWER(COALESCE(d.muscles,'')) LIKE ?"
            params.append(f"%{muscle.lower()}%")
        if favorites is not None:
            if favorites:
                sql += " AND exercises.id IN (SELECT exercise_id FROM favorites WHERE profile_id=?)"
            else:
                sql += " AND exercises.id NOT IN (SELECT exercise_id FROM favorites WHERE profile_id=?)"
            params.append(profile_id)
        sql += (" ORDER BY CASE exercises.category " +
                " ".join(f"WHEN '{c}' THEN {i}" for i, c in enumerate(CATEGORY_ORDER)) +
                " ELSE 99 END, exercises.difficulty, exercises.name")
        return fetch_all(self.db, sql, params)

    def exercise(self, ex_id):
        return fetch_one(self.db, "SELECT exercises.*, COALESCE(d.muscles,'') AS muscles, "
                                  "COALESCE(d.equipment,'') AS equipment FROM exercises "
                                  "LEFT JOIN exercise_details d ON d.exercise_id=exercises.id "
                                  "WHERE exercises.id=?", (ex_id,))

    def add_custom_exercise(self, name, category, difficulty, kind, sets, amount, rest, instructions=""):
        ex_id = "u_" + uuid.uuid4().hex[:8]
        self.db.execute(
            """INSERT INTO exercises(id,name,category,difficulty,kind,default_sets,default_amount,
               default_rest,instructions,skill_id,builtin) VALUES(?,?,?,?,?,?,?,?,?,NULL,0)""",
            (ex_id, name.strip(), category, difficulty, kind, sets, amount, rest, instructions.strip()))
        self.db.commit()
        return ex_id

    def delete_custom_exercise(self, ex_id):
        """Only user-made exercises that no workout uses can be deleted."""
        ex = self.exercise(ex_id)
        if not ex or ex["builtin"]:
            return False
        if fetch_one(self.db, "SELECT 1 AS x FROM workout_exercises WHERE exercise_id=?", (ex_id,)):
            return False
        self.db.execute("DELETE FROM exercises WHERE id=?", (ex_id,))
        self.db.commit()
        return True

    # ------------------------------------------------------------- workouts
    def workouts(self):
        return fetch_all(self.db, """SELECT w.*, (SELECT COUNT(*) FROM workout_exercises x
                          WHERE x.workout_id=w.id) AS n FROM workouts w ORDER BY LOWER(w.name)""")

    def workout(self, wid):
        w = fetch_one(self.db, "SELECT * FROM workouts WHERE id=?", (wid,))
        if not w:
            return None
        w["entries"] = fetch_all(self.db, """SELECT we.*, e.name, e.kind, e.category, e.difficulty,
            e.instructions FROM workout_exercises we JOIN exercises e ON e.id=we.exercise_id
            WHERE we.workout_id=? ORDER BY we.position""", (wid,))
        return w

    def save_workout(self, wid, name, description, style, entries):
        """Create (wid=None) or update a workout, replacing its exercise list."""
        name = name.strip()
        if not name:
            raise ValueError("A workout needs a name.")
        ts = now()
        with self.db:
            if wid is None:
                wid = self.db.execute(
                    "INSERT INTO workouts(name,description,style,created,updated) VALUES(?,?,?,?,?)",
                    (name, description.strip(), style, ts, ts)).lastrowid
            else:
                self.db.execute("UPDATE workouts SET name=?, description=?, style=?, updated=? WHERE id=?",
                                (name, description.strip(), style, ts, wid))
                self.db.execute("DELETE FROM workout_exercises WHERE workout_id=?", (wid,))
            for pos, e in enumerate(entries):
                self.db.execute(
                    """INSERT INTO workout_exercises(workout_id,position,exercise_id,sets,reps,hold_sec,
                       rest_sets,rest_after,note) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (wid, pos, e["exercise_id"], e["sets"], e["reps"], e["hold_sec"],
                     e["rest_sets"], e["rest_after"], e.get("note", "")))
        return wid

    def duplicate_workout(self, wid):
        w = self.workout(wid)
        return self.save_workout(None, f"{w['name']} (copy)", w["description"], w["style"], w["entries"])

    def delete_workout(self, wid):
        with self.db:
            self.db.execute("DELETE FROM workouts WHERE id=?", (wid,))

    def install_examples(self):
        """Create the example Push/Pull/Legs & Core/Skill workouts (reusing same-named ones)."""
        ids = {}
        existing = {w["name"]: w["id"] for w in self.workouts()}
        for name, desc, style, items in EXAMPLE_WORKOUTS:
            if name in existing:
                ids[name] = existing[name]
                continue
            entries = []
            for ex_id, sets, amount in items:
                ex = self.exercise(ex_id)
                d = entry_defaults(ex, style)
                d.update(exercise_id=ex_id, sets=sets, note="")
                d["hold_sec" if ex["kind"] == "hold" else "reps"] = amount
                entries.append(d)
            ids[name] = self.save_workout(None, name, desc, style, entries)
        return ids
