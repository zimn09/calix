"""Database glue for ranks (no Qt).

Ranks are never stored. They are always recomputed from recorded performances:
  * manual entries and confirmed workout sets       (table `performances`)
  * personal records logged in the skill tree       (table `records`)
  * skills marked completed in the tree             (only used by progression lines)
so history, deletions and imports always stay consistent.
"""
import datetime as dt
from collections import defaultdict

from database import fetch_all
from ranks import RANKS, build_tracks, evaluate_line, evaluate_single
from skills_data import SKILLS_BY_ID


class RankRepo:
    def __init__(self, store, wrepo):
        self.store, self.db, self.wrepo = store, store.db, wrepo
        exercises = wrepo.exercises()
        self.names = {e["id"]: e["name"] for e in exercises}
        self.tracks = build_tracks(exercises)
        self.by_id = {t.id: t for t in self.tracks}
        self.by_exercise = {t.exercise_id: t for t in self.tracks if t.metric != "line"}
        self._skill_ex = defaultdict(list)          # skill id -> exercise ids with the same unit
        for e in exercises:
            sk = SKILLS_BY_ID.get(e["skill_id"] or "")
            if sk and sk.unit == ("reps" if e["kind"] == "reps" else "s"):
                self._skill_ex[sk.id].append(e["id"])
        self._subs = []

    def subscribe(self, fn):
        self._subs.append(fn)

    def _notify(self):
        for fn in list(self._subs):
            fn()

    # ------------------------------------------------------------ evaluation
    def _events(self):
        events = [(r["logged"][:10], r["exercise_id"], r["value"])
                  for r in fetch_all(self.db, "SELECT exercise_id, value, logged FROM performances")]
        for r in fetch_all(self.db, "SELECT skill_id, value, logged FROM records"):
            events += [(r["logged"][:10], ex, r["value"]) for ex in self._skill_ex.get(r["skill_id"], [])]
        passed = [(r["updated"][:10], ex) for r in
                  fetch_all(self.db, "SELECT skill_id, updated FROM progress WHERE status='completed'")
                  for ex in self._skill_ex.get(r["skill_id"], [])]
        return events, passed

    def evaluate_all(self):
        """{track id: TrackResult}"""
        events, passed = self._events()
        by_ex = defaultdict(list)
        for d, ex, v in events:
            by_ex[ex].append((d, v))
        out = {}
        for t in self.tracks:
            if t.metric == "line":
                ids = {s.exercise_id for s in t.steps}
                out[t.id] = evaluate_line(t, [(d, ex, v) for ex in ids for d, v in by_ex.get(ex, [])],
                                          [(d, ex) for d, ex in passed if ex in ids])
            else:
                out[t.id] = evaluate_single(t, by_ex.get(t.exercise_id, []))
        return out

    def results(self):
        return list(self.evaluate_all().values())

    def result_for_exercise(self, exercise_id, all_results=None):
        t = self.by_exercise.get(exercise_id)
        return (all_results or self.evaluate_all())[t.id] if t else None

    def results_for_skill(self, skill_id):
        res = self.evaluate_all()
        return [res[self.by_exercise[ex].id] for ex in self._skill_ex.get(skill_id, []) if ex in self.by_exercise]

    def skill_ranks(self):
        """{skill id: best rank index} used for badges on skill-tree nodes."""
        res, out = self.evaluate_all(), {}
        for sid, exs in self._skill_ex.items():
            ranks = [res[self.by_exercise[e].id].rank for e in exs if e in self.by_exercise]
            if ranks:
                out[sid] = max(ranks)
        return out

    def tracks_with_exercise(self, exercise_id):
        return [t for t in self.tracks if t.exercise_id == exercise_id or
                any(s.exercise_id == exercise_id for s in t.steps)]

    def max_plausible(self, exercise_id):
        """Largest value accepted for an exercise (4x the top-rank threshold), to catch typos like 999 reps."""
        t = self.by_exercise.get(exercise_id)
        return int(t.thresholds[-1] * 4) if t else 0

    def best_values(self):
        """{exercise id: best value ever recorded} from performances and skill-tree records."""
        events, _ = self._events()
        out = {}
        for _, ex, v in events:
            out[ex] = max(out.get(ex, 0), v)
        return out

    def pr_events(self):
        """Personal records derived from history: a day whose best beats everything recorded on earlier days.

        At most one per exercise per day; the very first recording is never a record.
        """
        events, _ = self._events()
        days = defaultdict(lambda: defaultdict(float))
        for d, ex, v in events:
            if ex in self.by_exercise:
                days[ex][d] = max(days[ex][d], v)
        out = []
        for ex, per_day in days.items():
            best, t = 0.0, self.by_exercise[ex]
            for d in sorted(per_day):
                if per_day[d] > best:
                    if best > 0:
                        out.append(dict(exercise_id=ex, date=d, value=per_day[d], previous=best,
                                        name=self.names[ex], difficulty=t.difficulty, unit=t.unit))
                    best = per_day[d]
        return out

    # ----------------------------------------------------------- performances
    @staticmethod
    def _diff(before, after, only=None):
        changes = []
        for tid, a in after.items():
            if only is not None and tid not in only:
                continue
            b = before[tid]
            if a.rank != b.rank:
                changes.append(dict(track=a.track.name, track_id=tid, before=b.rank, after=a.rank,
                                    up=a.rank > b.rank, value=a.best, unit=a.track.unit))
        return changes

    def log_performance(self, exercise_id, value, day=None, source="manual", session_id=None, note=""):
        """Record a performance and return the rank changes it caused."""
        if exercise_id not in self.by_exercise:
            raise ValueError("This exercise has no rank ladder.")
        value = float(value)
        if value <= 0:
            raise ValueError("Enter a value greater than zero.")
        cap = self.max_plausible(exercise_id)
        if value > cap:
            raise ValueError(f"That value looks unrealistic (the maximum accepted is {cap} {self.by_exercise[exercise_id].unit}).")
        before = self.evaluate_all()
        self.db.execute("INSERT INTO performances(exercise_id,value,logged,source,session_id,note) VALUES(?,?,?,?,?,?)",
                        (exercise_id, value, (day or dt.date.today()).isoformat(), source, session_id, note.strip()))
        self.db.commit()
        changes = self._diff(before, self.evaluate_all(), {t.id for t in self.tracks_with_exercise(exercise_id)})
        self._notify()
        return changes

    def record_session(self, sid, items):
        """Confirm real performances from a finished workout.

        items: [{exercise_id, set_id, value}] chosen by the user. Writes the confirmed value back into the
        set, records a performance, and updates the linked skill-tree record when it is a new best.
        """
        day = self.db.execute("SELECT session_date FROM sessions WHERE id=?", (sid,)).fetchone()[0]
        before = self.evaluate_all()
        with self.db:
            for it in items:
                if it["exercise_id"] not in self.by_exercise or not 0 < it["value"] <= self.max_plausible(it["exercise_id"]):
                    continue
                kind = self.by_exercise[it["exercise_id"]].metric
                col = "hold" if kind == "hold" else "reps"
                self.db.execute(f"UPDATE session_sets SET {col}=?, confirmed=1 WHERE id=?", (int(it["value"]), it["set_id"]))
                self.db.execute("INSERT INTO performances(exercise_id,value,logged,source,session_id) VALUES(?,?,?,?,?)",
                                (it["exercise_id"], float(it["value"]), day, "workout", sid))
        for it in items:
            ex = self.wrepo.exercise(it["exercise_id"])
            if ex and ex["skill_id"] and it["exercise_id"] in self._skill_ex.get(ex["skill_id"], []) \
                    and it["value"] > (self.store.best(ex["skill_id"]) or 0):
                self.store.add_record(ex["skill_id"], it["value"])
        changes = self._diff(before, self.evaluate_all())
        self._notify()
        return changes

    def performances(self, exercise_id=None, limit=100):
        sql = "SELECT * FROM performances"
        params = []
        if exercise_id:
            sql += " WHERE exercise_id=?"
            params.append(exercise_id)
        rows = fetch_all(self.db, sql + " ORDER BY logged DESC, id DESC LIMIT ?", (*params, limit))
        for r in rows:
            r["name"] = self.names.get(r["exercise_id"], r["exercise_id"])
        return rows

    def delete_performance(self, pid):
        self.db.execute("DELETE FROM performances WHERE id=?", (pid,))
        self.db.commit()
        self._notify()

    def import_history(self):
        """Explicitly import the best set per exercise from past completed workouts. Returns how many were added."""
        n = 0
        sessions = fetch_all(self.db, "SELECT id, session_date FROM sessions WHERE status='completed'")
        for s in sessions:
            for b in self._best_sets(s["id"]):
                if b["exercise_id"] not in self.by_exercise or b["value"] <= 0:
                    continue
                if self.db.execute("SELECT 1 FROM performances WHERE session_id=? AND exercise_id=?",
                                   (s["id"], b["exercise_id"])).fetchone():
                    continue
                self.db.execute("INSERT INTO performances(exercise_id,value,logged,source,session_id) VALUES(?,?,?,?,?)",
                                (b["exercise_id"], b["value"], s["session_date"], "workout", s["id"]))
                self.db.execute("UPDATE session_sets SET confirmed=1 WHERE id=?", (b["set_id"],))
                n += 1
        self.db.commit()
        if n:
            self._notify()
        return n

    def _best_sets(self, sid):
        best = {}
        for r in fetch_all(self.db, """SELECT id AS set_id, exercise_id,
                CASE WHEN kind='reps' THEN reps ELSE hold END AS value FROM session_sets
                WHERE session_id=? AND done=1""", (sid,)):
            if r["exercise_id"] not in best or r["value"] > best[r["exercise_id"]]["value"]:
                best[r["exercise_id"]] = r
        return list(best.values())

    @staticmethod
    def rank_name(i):
        return RANKS[i][0]
