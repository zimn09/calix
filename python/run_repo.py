"""Running log: distance, time and pace (no Qt).

A run is stored as a completed session with ``distance_m`` filled in, so it shows
up in History, streaks, weekly charts and XP exactly like any other workout.
"""
import datetime as dt

from database import fetch_all, fetch_one
from workouts import now


def pace_seconds(distance_m, duration_sec):
    """Seconds per kilometre, or None when the run has no usable data."""
    if not distance_m or not duration_sec:
        return None
    return duration_sec * 1000.0 / distance_m


def fmt_pace(seconds_per_km):
    """Pace as m:ss (per kilometre)."""
    if not seconds_per_km:
        return "–"
    m, s = divmod(int(round(seconds_per_km)), 60)
    return f"{m}:{s:02d}"


def fmt_distance(distance_m):
    return f"{distance_m / 1000:.2f} km"


def fmt_time(sec):
    """Duration as mm:ss, or h:mm:ss for runs over an hour."""
    m, s = divmod(int(max(0, sec)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class RunRepo:
    """Runs live in the sessions table; ``distance_m > 0`` marks a run."""

    def __init__(self, store):
        self.store, self.db = store, store.db

    def log(self, distance_m, duration_sec, run_date=None, note=""):
        """Save a finished run and return its session id."""
        distance_m, duration_sec = int(distance_m), int(duration_sec)
        if distance_m <= 0:
            raise ValueError("A run needs a distance.")
        if duration_sec <= 0:
            raise ValueError("A run needs a time.")
        day = (run_date or dt.date.today()).isoformat()
        ts = now()
        import json
        with self.db:
            return self.db.execute(
                """INSERT INTO sessions(workout_id,workout_name,session_date,started,ended,status,
                   elapsed_sec,state_json,entry_id,distance_m)
                   VALUES(NULL,'Run',?,?,?,'completed',?,?,NULL,?)""",
                (day, ts, ts, duration_sec, json.dumps({"note": note, "run": True}), distance_m)).lastrowid

    def runs(self, limit=300):
        return fetch_all(self.db, """SELECT * FROM sessions
            WHERE status='completed' AND distance_m>0
            ORDER BY session_date DESC, id DESC LIMIT ?""", (limit,))

    def totals(self):
        row = fetch_one(self.db, """SELECT COUNT(*) AS n, COALESCE(SUM(distance_m),0) AS distance,
            COALESCE(SUM(elapsed_sec),0) AS seconds FROM sessions
            WHERE status='completed' AND distance_m>0""")
        best = fetch_one(self.db, """SELECT MIN(elapsed_sec * 1000.0 / distance_m) AS p FROM sessions
            WHERE status='completed' AND distance_m>0 AND elapsed_sec>0""")
        avg = pace_seconds(row["distance"], row["seconds"])
        return dict(count=row["n"], distance=row["distance"], seconds=row["seconds"],
                    average=avg, best=best["p"] if best else None)

    def delete(self, sid):
        self.db.execute("DELETE FROM sessions WHERE id=? AND distance_m>0", (sid,))
        self.db.commit()
