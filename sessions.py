"""Workout sessions (no Qt).

A session and all of its planned sets are written to the database the moment a
workout starts, and every change is saved immediately. A session with status
'active' can therefore always be resumed after an interruption or app restart.
"""
import datetime as dt
import json

from database import fetch_all, fetch_one
from workouts import now

SET_FIELDS = ("reps", "hold", "rest_sec", "done")


class SessionRepo:
    def __init__(self, store, wrepo):
        self.store, self.db, self.wrepo = store, store.db, wrepo

    # ------------------------------------------------------------ lifecycle
    def active(self):
        return fetch_one(self.db, "SELECT * FROM sessions WHERE status='active' ORDER BY id DESC LIMIT 1")

    def start(self, workout_id, entry_id=None):
        if self.active():
            raise RuntimeError("A session is already in progress.")
        w = self.wrepo.workout(workout_id)
        if not w or not w["entries"]:
            raise ValueError("This workout has no exercises.")
        entries = w["entries"]
        with self.db:
            sid = self.db.execute(
                """INSERT INTO sessions(workout_id,workout_name,session_date,started,status,elapsed_sec,
                   state_json,entry_id) VALUES(?,?,?,?, 'active',0,'{}',?)""",
                (workout_id, w["name"], dt.date.today().isoformat(), now(), entry_id)).lastrowid
            for pos, e in enumerate(entries):
                for i in range(e["sets"]):
                    last_set = i == e["sets"] - 1
                    rest = e["rest_after"] if last_set else e["rest_sets"]
                    if pos == len(entries) - 1 and last_set:
                        rest = 0
                    self.db.execute(
                        """INSERT INTO session_sets(session_id,ex_pos,set_idx,exercise_id,exercise_name,kind,
                           target_reps,target_hold,reps,hold,rest_sec,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (sid, pos, i, e["exercise_id"], e["name"], e["kind"], e["reps"], e["hold_sec"],
                         e["reps"], e["hold_sec"], rest, e["note"]))
        return sid

    def sets(self, sid):
        return fetch_all(self.db, "SELECT * FROM session_sets WHERE session_id=? ORDER BY ex_pos, set_idx", (sid,))

    def update_set(self, set_id, **fields):
        fields = {k: int(v) for k, v in fields.items() if k in SET_FIELDS}
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        extra = ""
        if "done" in fields:
            extra = ", done_at=" + ("datetime('now','localtime')" if fields["done"] else "NULL")
        self.db.execute(f"UPDATE session_sets SET {cols}{extra} WHERE id=?", (*fields.values(), set_id))
        self.db.commit()

    def save_state(self, sid, elapsed, state):
        self.db.execute("UPDATE sessions SET elapsed_sec=?, state_json=? WHERE id=?",
                        (int(elapsed), json.dumps(state), sid))
        self.db.commit()

    def load_state(self, session):
        try:
            return json.loads(session.get("state_json") or "{}")
        except ValueError:
            return {}

    def discard(self, sid):
        self.db.execute("DELETE FROM sessions WHERE id=?", (sid,))
        self.db.commit()

    def finish(self, sid, elapsed):
        """Mark a session completed. Returns a summary dict (None if nothing was done, which discards it)."""
        done = fetch_one(self.db, "SELECT COUNT(*) AS n FROM session_sets WHERE session_id=? AND done=1", (sid,))
        if not done["n"]:
            self.discard(sid)
            return None
        prs = self.new_prs(sid)
        self.db.execute("UPDATE sessions SET status='completed', ended=?, elapsed_sec=? WHERE id=?",
                        (now(), int(elapsed), sid))
        self.db.commit()
        s = self.summary(sid)
        s["prs"] = prs
        return s

    # ------------------------------------------------------------- analysis
    def new_prs(self, sid):
        """Exercises where this session beat the best earlier completed session."""
        out = []
        rows = fetch_all(self.db, """SELECT exercise_id, MAX(exercise_name) AS name, kind,
            MAX(CASE WHEN kind='reps' THEN reps ELSE hold END) AS best FROM session_sets
            WHERE session_id=? AND done=1 GROUP BY exercise_id, kind""", (sid,))
        for r in rows:
            prev = fetch_one(self.db, """SELECT MAX(CASE WHEN ss.kind='reps' THEN ss.reps ELSE ss.hold END) AS p
                FROM session_sets ss JOIN sessions s ON s.id=ss.session_id
                WHERE s.status='completed' AND ss.done=1 AND ss.exercise_id=? AND ss.kind=? AND s.id!=?""",
                             (r["exercise_id"], r["kind"], sid))["p"]
            if prev and r["best"] > prev:
                out.append(dict(name=r["name"], value=r["best"], previous=prev,
                                unit="reps" if r["kind"] == "reps" else "s"))
        return out

    def best_sets(self, sid):
        """Best completed set per exercise (the value a user can confirm as a real performance)."""
        best = {}
        for r in fetch_all(self.db, """SELECT id AS set_id, exercise_id, exercise_name AS name, kind,
                CASE WHEN kind='reps' THEN reps ELSE hold END AS value
                FROM session_sets WHERE session_id=? AND done=1 ORDER BY ex_pos, set_idx""", (sid,)):
            if r["exercise_id"] not in best or r["value"] > best[r["exercise_id"]]["value"]:
                best[r["exercise_id"]] = r
        return list(best.values())

    def summary(self, sid):
        return fetch_one(self.db, """SELECT s.id, s.workout_name, s.session_date, s.elapsed_sec,
            COUNT(ss.id) AS sets_total, COALESCE(SUM(ss.done),0) AS sets_done,
            COALESCE(SUM(CASE WHEN ss.done=1 AND ss.kind='reps' THEN ss.reps ELSE 0 END),0) AS reps_total,
            COALESCE(SUM(CASE WHEN ss.done=1 AND ss.kind='hold' THEN ss.hold ELSE 0 END),0) AS hold_total,
            COUNT(DISTINCT CASE WHEN ss.done=1 THEN ss.exercise_id END) AS exercises_done
            FROM sessions s LEFT JOIN session_sets ss ON ss.session_id=s.id WHERE s.id=? GROUP BY s.id""", (sid,))

    def history(self, limit=500):
        return fetch_all(self.db, """SELECT s.id, s.workout_id, s.workout_name, s.session_date, s.started,
            s.elapsed_sec, COUNT(ss.id) AS sets_total, COALESCE(SUM(ss.done),0) AS sets_done,
            COALESCE(SUM(CASE WHEN ss.done=1 AND ss.kind='reps' THEN ss.reps ELSE 0 END),0) AS reps_total,
            COALESCE(SUM(CASE WHEN ss.done=1 AND ss.kind='hold' THEN ss.hold ELSE 0 END),0) AS hold_total
            FROM sessions s LEFT JOIN session_sets ss ON ss.session_id=s.id
            WHERE s.status='completed' GROUP BY s.id ORDER BY s.started DESC LIMIT ?""", (limit,))

    def delete_session(self, sid):
        self.discard(sid)

    def delete_all_history(self):
        self.db.execute("DELETE FROM sessions WHERE status='completed'")
        self.db.commit()

    def completed_on(self, start, end):
        """{date: set(workout_id)} of completed sessions in a date range."""
        out = {}
        for r in fetch_all(self.db, """SELECT session_date, workout_id FROM sessions WHERE status='completed'
                                       AND session_date BETWEEN ? AND ?""",
                           (start.isoformat(), end.isoformat())):
            out.setdefault(dt.date.fromisoformat(r["session_date"]), set()).add(r["workout_id"])
        return out
