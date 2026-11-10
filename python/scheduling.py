"""Weekly routines and one-time scheduled sessions (no Qt).

Entry kinds
  weekly : repeats every `weekday` (0=Monday) from the day it was created
  once   : happens on `on_date`
An entry is either a workout (workout_id) or a rest day (is_rest=1).
A single occurrence of a weekly entry can be skipped via schedule_skips.
"""
import datetime as dt

from database import fetch_all, fetch_one

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _d(v):
    return v if isinstance(v, dt.date) else dt.date.fromisoformat(str(v))


class ScheduleRepo:
    def __init__(self, db):
        self.db = db

    # ----------------------------------------------------------------- CRUD
    def _check(self, kind, weekday, on_date, workout_id, is_rest):
        if kind == "weekly" and weekday not in range(7):
            raise ValueError("Pick a weekday.")
        if kind == "once" and on_date is None:
            raise ValueError("Pick a date.")
        if kind not in ("weekly", "once"):
            raise ValueError("Unknown schedule kind.")
        if not is_rest and workout_id is None:
            raise ValueError("Pick a workout or mark a rest day.")

    def add_entry(self, kind, weekday=None, on_date=None, workout_id=None, is_rest=False, note=""):
        self._check(kind, weekday, on_date, workout_id, is_rest)
        cur = self.db.execute(
            """INSERT INTO schedule_entries(kind,weekday,on_date,workout_id,is_rest,note,created)
               VALUES(?,?,?,?,?,?,?)""",
            (kind, weekday if kind == "weekly" else None,
             _d(on_date).isoformat() if kind == "once" else None,
             None if is_rest else workout_id, int(bool(is_rest)), note.strip(), dt.date.today().isoformat()))
        self.db.commit()
        return cur.lastrowid

    def update_entry(self, entry_id, kind, weekday=None, on_date=None, workout_id=None, is_rest=False, note=""):
        self._check(kind, weekday, on_date, workout_id, is_rest)
        self.db.execute(
            """UPDATE schedule_entries SET kind=?, weekday=?, on_date=?, workout_id=?, is_rest=?, note=?
               WHERE id=?""",
            (kind, weekday if kind == "weekly" else None,
             _d(on_date).isoformat() if kind == "once" else None,
             None if is_rest else workout_id, int(bool(is_rest)), note.strip(), entry_id))
        self.db.execute("DELETE FROM schedule_skips WHERE entry_id=?", (entry_id,))
        self.db.commit()

    def delete_entry(self, entry_id):
        self.db.execute("DELETE FROM schedule_entries WHERE id=?", (entry_id,))
        self.db.commit()

    def clear_weekly(self):
        self.db.execute("DELETE FROM schedule_entries WHERE kind='weekly'")
        self.db.commit()

    def skip(self, entry_id, day):
        self.db.execute("INSERT OR IGNORE INTO schedule_skips VALUES(?,?)", (entry_id, _d(day).isoformat()))
        self.db.commit()

    def entry(self, entry_id):
        return fetch_one(self.db, """SELECT s.*, w.name AS workout_name, w.style FROM schedule_entries s
                         LEFT JOIN workouts w ON w.id=s.workout_id WHERE s.id=?""", (entry_id,))

    def weekly_entries(self):
        return fetch_all(self.db, """SELECT s.*, w.name AS workout_name, w.style FROM schedule_entries s
            LEFT JOIN workouts w ON w.id=s.workout_id WHERE s.kind='weekly'
            ORDER BY s.weekday, s.is_rest, LOWER(COALESCE(w.name,''))""")

    # ---------------------------------------------------------- occurrences
    def occurrences(self, start, end, done_map=None):
        """{date: [occurrence dicts]} for start..end inclusive.

        done_map: {date: set(workout_id)} of completed sessions, used to flag `done`.
        """
        start, end = _d(start), _d(end)
        done_map = done_map or {}
        entries = fetch_all(self.db, """SELECT s.*, w.name AS workout_name, w.style FROM schedule_entries s
                            LEFT JOIN workouts w ON w.id=s.workout_id ORDER BY s.is_rest, s.id""")
        skips = {(r["entry_id"], r["on_date"]) for r in fetch_all(self.db, "SELECT * FROM schedule_skips")}
        out, day = {}, start
        while day <= end:
            out[day] = []
            day += dt.timedelta(days=1)
        for e in entries:
            if e["kind"] == "once":
                days = [_d(e["on_date"])] if start <= _d(e["on_date"]) <= end else []
            else:
                first = max(start, _d(e["created"]))
                shift = (e["weekday"] - first.weekday()) % 7
                days, d = [], first + dt.timedelta(days=shift)
                while d <= end:
                    days.append(d)
                    d += dt.timedelta(days=7)
            for d in days:
                if (e["id"], d.isoformat()) in skips:
                    continue
                out[d].append(dict(
                    entry_id=e["id"], kind=e["kind"], workout_id=e["workout_id"],
                    workout_name=e["workout_name"], style=e["style"], is_rest=bool(e["is_rest"]),
                    note=e["note"], date=d,
                    done=(not e["is_rest"]) and e["workout_id"] in done_map.get(d, ())))
        return out

    def for_date(self, day, done_map=None):
        return self.occurrences(day, day, done_map)[_d(day)]

    def upcoming(self, start, days=14, done_map=None, limit=6):
        """Not-yet-done workout occurrences from `start` onward, soonest first."""
        end = _d(start) + dt.timedelta(days=days)
        occ = self.occurrences(start, end, done_map)
        return [o for d in sorted(occ) for o in occ[d] if not o["is_rest"] and not o["done"]][:limit]

    # ------------------------------------------------------ edit occurrences
    def move_occurrence(self, occ, new_date):
        new_date = _d(new_date)
        if new_date == occ["date"]:
            return
        if occ["kind"] == "once":
            self.db.execute("UPDATE schedule_entries SET on_date=? WHERE id=?",
                            (new_date.isoformat(), occ["entry_id"]))
            self.db.commit()
        else:
            self.skip(occ["entry_id"], occ["date"])
            self.add_entry("once", on_date=new_date, workout_id=occ["workout_id"],
                           is_rest=occ["is_rest"], note=occ["note"])

    def remove_occurrence(self, occ, all_weeks=False):
        if occ["kind"] == "once" or all_weeks:
            self.delete_entry(occ["entry_id"])
        else:
            self.skip(occ["entry_id"], occ["date"])


def install_example_routine(wrepo, srepo):
    """Mon push, Tue pull, Wed rest, Thu legs & core, Sat skill training."""
    ids = wrepo.install_examples()
    plan = [(0, "Push Day"), (1, "Pull Day"), (3, "Legs & Core"), (5, "Skill Training")]
    have = {(e["weekday"], e["workout_id"], e["is_rest"]) for e in srepo.weekly_entries()}
    for wd, name in plan:
        if (wd, ids[name], 0) not in have:
            srepo.add_entry("weekly", weekday=wd, workout_id=ids[name])
    if (2, None, 1) not in have:
        srepo.add_entry("weekly", weekday=2, is_rest=True)
    return ids
