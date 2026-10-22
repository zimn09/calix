"""XP, levels and achievements computed from real recorded data (no Qt).

The engine never trusts events or button clicks. `sync()` re-reads the real data
(finished workouts, recorded performances, ranks, skill-tree progress) and credits
anything that has not been credited yet. Every reward has a deterministic key
(`workout:12`, `pr:pullup:2026-10-20`, `rank:pullup:4`, `skill_done:pushup` ...) that is
unique in the ledger, so reopening the app, re-reading a finished workout or clicking
buttons repeatedly can never credit the same achievement twice. The ledger is
append-only: XP is not taken back if data is later deleted.
"""
import datetime as dt
import math
from collections import Counter
from dataclasses import dataclass, field

import achievements as AC
import progression as P
import stats
from database import fetch_all, fetch_one
from ranks import RANKS

CATEGORY_LABELS = {"workout": "Workout", "set": "Sets & exercises", "record": "Personal record",
                   "rank": "Rank", "skill": "Skill tree", "achievement": "Achievement"}


@dataclass
class SyncResult:
    level_before: P.LevelInfo
    level_after: P.LevelInfo = None
    awards: list = field(default_factory=list)       # [{amount, reason, category, earned_on}]
    unlocked: list = field(default_factory=list)     # [Achievement]

    @property
    def gained(self):
        return sum(a["amount"] for a in self.awards)

    @property
    def leveled_up(self):
        return self.level_after.level > self.level_before.level

    @property
    def empty(self):
        return not self.awards and not self.unlocked


def _longest_run(days, step):
    """Longest run of consecutive items spaced `step` days apart (days: sorted unique dates)."""
    best = run = 0
    prev = None
    for d in days:
        run = run + 1 if prev is not None and (d - prev).days == step else 1
        best, prev = max(best, run), d
    return best


class XpEngine:
    def __init__(self, store, wrepo, sess, ranks, graph):
        self.store, self.db, self.wrepo, self.sess = store, store.db, wrepo, sess
        self.ranks, self.graph = ranks, graph
        self._ex_skill = {e["id"]: e["skill_id"] for e in wrepo.exercises() if e["skill_id"]}
        self._subs = []

    def subscribe(self, fn):
        self._subs.append(fn)

    # ----------------------------------------------------------------- reading
    def total_xp(self):
        return fetch_one(self.db, "SELECT COALESCE(SUM(amount),0) AS t FROM xp_events")["t"]

    def level(self):
        return P.level_info(self.total_xp())

    def history(self, category=None, limit=500):
        sql, params = "SELECT * FROM xp_events", []
        if category:
            sql += " WHERE category=?"
            params.append(category)
        return fetch_all(self.db, sql + " ORDER BY earned_on DESC, id DESC LIMIT ?", (*params, limit))

    def breakdown(self):
        """{category: total XP}"""
        return {r["category"]: r["t"] for r in fetch_all(
            self.db, "SELECT category, SUM(amount) AS t FROM xp_events GROUP BY category")}

    def achievement_rows(self):
        """Every achievement with its saved progress and unlock date."""
        state = {r["id"]: r for r in fetch_all(self.db, "SELECT * FROM achievements")}
        rows = []
        for a in AC.ACHIEVEMENTS:
            s = state.get(a.id)
            prog = s["progress"] if s else 0.0
            rows.append(dict(a=a, progress=prog, unlocked=s["unlocked"] if s else None,
                             pct=min(1.0, prog / a.target) if a.target else 0.0))
        return rows

    def nearest(self, n=3):
        """Locked achievements closest to completion (those already started first)."""
        locked = [r for r in self.achievement_rows() if r["unlocked"] is None]
        started = sorted((r for r in locked if r["progress"] > 0), key=lambda r: (-r["pct"], -r["a"].xp))
        rest = sorted((r for r in locked if r["progress"] <= 0), key=lambda r: (r["a"].xp, r["a"].target))
        return (started + rest)[:n]

    def achievements_for_skill(self, skill_id):
        rows = self.achievement_rows()
        return [r for r in rows if skill_id in r["a"].skills
                or any(self._ex_skill.get(ex) == skill_id for ex in r["a"].exercises)]

    def profile(self):
        """Everything the profile/dashboard needs about level and achievements."""
        lvl = self.level()
        rows = self.achievement_rows()
        return dict(level=lvl.level, title=lvl.title, color=lvl.color, total=lvl.total, into=lvl.into,
                    need=lvl.need, progress=lvl.progress, next_title=lvl.next_title,
                    next_title_level=lvl.next_title_level,
                    unlocked=sum(1 for r in rows if r["unlocked"]), count=len(rows))

    # -------------------------------------------------------------------- sync
    def sync(self):
        """Credit everything real that is not credited yet. Safe to call at any time, any number of times."""
        res = SyncResult(level_before=self.level())
        self._award_sessions(res)
        self._award_records(res)
        self._award_ranks(res)
        self._award_skills(res)
        base = self._base_metrics()
        for _ in range(8):                          # achievements pay XP, which may unlock level achievements
            if not self._update_achievements(res, base):
                break
        res.level_after = self.level()
        self.db.execute("INSERT OR REPLACE INTO xp_state(id,total_xp,level,title,updated) VALUES(1,?,?,?,?)",
                        (res.level_after.total, res.level_after.level, res.level_after.title,
                         dt.datetime.now().isoformat(timespec="seconds")))
        self.db.commit()
        if not res.empty:
            for fn in list(self._subs):
                fn()
        return res

    def _award(self, res, key, amount, reason, category, earned_on):
        if amount <= 0:
            return
        cur = self.db.execute(
            "INSERT OR IGNORE INTO xp_events(key,amount,reason,category,earned_on,awarded) VALUES(?,?,?,?,?,?)",
            (key, int(amount), reason, category, earned_on, dt.datetime.now().isoformat(timespec="seconds")))
        if cur.rowcount:
            res.awards.append(dict(amount=int(amount), reason=reason, category=category, earned_on=earned_on))

    # ---- workouts
    def qualifying_sessions(self):
        """Finished workouts that really happened: >= half of the planned sets done and >= 2 minutes long."""
        full = Counter()
        for r in fetch_all(self.db, "SELECT session_id, ex_pos, MIN(done) AS full FROM session_sets "
                                    "GROUP BY session_id, ex_pos"):
            if r["full"]:
                full[r["session_id"]] += 1
        entry = {r["id"]: r["entry_id"] for r in
                 fetch_all(self.db, "SELECT id, entry_id FROM sessions WHERE status='completed'")}
        out = []
        for r in sorted(self.sess.history(100000), key=lambda r: (r["session_date"], r["id"])):
            need = max(1, math.ceil(r["sets_total"] * P.MIN_SETS_SHARE))
            if r["sets_done"] >= need and r["elapsed_sec"] >= P.MIN_SESSION_SECONDS:
                out.append(dict(r, full_exercises=full[r["id"]], entry_id=entry.get(r["id"])))
        return out

    def _award_sessions(self, res):
        per_day = Counter()
        for r in self.qualifying_sessions():
            day = r["session_date"]
            per_day[day] += 1
            if per_day[day] > P.SESSION_DAILY_CAP:      # anti-farming: only the first 3 workouts a day pay
                continue
            sid, name = r["id"], r["workout_name"]
            self._award(res, f"workout:{sid}", P.XP_WORKOUT, f"Workout completed: {name}", "workout", day)
            n = min(r["sets_done"], P.MAX_SET_XP)
            self._award(res, f"sets:{sid}", n * P.XP_PER_SET, f"{r['sets_done']} sets completed ({name})", "set", day)
            e = min(r["full_exercises"], P.MAX_EXERCISES_XP)
            self._award(res, f"exercises:{sid}", e * P.XP_PER_EXERCISE,
                        f"{r['full_exercises']} exercises completed in full ({name})", "set", day)
            if r["entry_id"] is not None and r["sets_done"] >= math.ceil(r["sets_total"] * 0.8):
                self._award(res, f"scheduled:{sid}", P.XP_SCHEDULED, f"Scheduled workout completed: {name}", "workout", day)

    # ---- records, ranks, skills
    def _award_records(self, res):
        for pr in self.ranks.pr_events():
            self._award(res, f"pr:{pr['exercise_id']}:{pr['date']}", P.XP_PR[pr["difficulty"]],
                        f"Personal record: {pr['name']} {pr['value']:g} {pr['unit']} (was {pr['previous']:g})",
                        "record", pr["date"])

    def _award_ranks(self, res):
        today = dt.date.today().isoformat()
        for tid, r in self.ranks.evaluate_all().items():
            for rank in range(1, r.rank + 1):
                when = next((h.date for h in r.history if h.rank >= rank), today)
                self._award(res, f"rank:{tid}:{rank}", P.rank_xp(rank, r.track.difficulty, r.track.metric == "line"),
                            f"Rank reached: {r.track.name} → {RANKS[rank][0]}", "rank", when)

    def _award_skills(self, res):
        rows = {r["skill_id"]: (r["status"], r["updated"][:10])
                for r in fetch_all(self.db, "SELECT skill_id, status, updated FROM progress")}
        done = {sid for sid, (st, _) in rows.items() if st == "completed" and sid in self.graph.skills}
        for sid in done:
            sk = self.graph.skills[sid]
            self._award(res, f"skill_done:{sid}", P.XP_SKILL_DONE[sk.tier], f"Skill completed: {sk.name}",
                        "skill", rows[sid][1])
        for sid, sk in self.graph.skills.items():
            # starting skills have no prerequisites: nothing was "unlocked", so no XP for them
            if sk.prereqs and all(p in done for p in sk.prereqs):
                self._award(res, f"skill_unlock:{sid}", P.XP_SKILL_UNLOCK[sk.tier], f"Skill unlocked: {sk.name}",
                            "skill", max(rows[p][1] for p in sk.prereqs))

    # ---- achievements
    def _base_metrics(self):
        """Metrics that only change when real data changes (computed once per sync)."""
        m = {}
        q = self.qualifying_sessions()
        hist = self.sess.history(100000)
        m["workouts"] = len(q)
        m["scheduled"] = sum(1 for r in q if r["entry_id"] is not None)
        m["sets"] = sum(r["sets_done"] for r in hist)
        m["reps"] = sum(r["reps_total"] for r in hist)
        m["hold_seconds"] = sum(r["hold_total"] for r in hist)
        dates = [dt.date.fromisoformat(r["session_date"]) for r in q]
        weeks = Counter(stats.week_start(d) for d in dates)
        m["week_best"] = max(weeks.values(), default=0)
        m["month_best"] = max(Counter((d.year, d.month) for d in dates).values(), default=0)
        m["streak_days"] = _longest_run(sorted(set(dates)), 1)
        m["week_streak"] = _longest_run(sorted(w for w, n in weeks.items() if n >= 3), 7)
        for ex, v in self.ranks.best_values().items():
            m[f"best:{ex}"] = v
        singles = [r for r in self.ranks.evaluate_all().values() if r.track.metric != "line"]
        for n in range(1, len(RANKS)):
            m[f"ranks_ge:{n}"] = sum(1 for r in singles if r.rank >= n)
        done = {r["skill_id"] for r in fetch_all(self.db, "SELECT skill_id FROM progress WHERE status='completed'")
                if r["skill_id"] in self.graph.skills}
        m["skills_done"] = len(done)
        for sid in done:
            sk = self.graph.skills[sid]
            m[f"skill:{sid}"] = 1
            m[f"skills_tier:{sk.tier}"] = m.get(f"skills_tier:{sk.tier}", 0) + 1
            m[f"skills_cat:{sk.category}"] = m.get(f"skills_cat:{sk.category}", 0) + 1
        m.update(self._library_metrics())
        return m

    def _library_metrics(self):
        """Metrics that come from the exercise library.

        Only *confirmed* performances count (the values the player confirmed in a
        workout or logged by hand). A ticked-but-unconfirmed set is not real
        training data and must never pay XP.
        """
        m = {}
        trained = {r["exercise_id"] for r in
                   fetch_all(self.db, "SELECT DISTINCT exercise_id FROM performances")}
        trained = {e for e in trained if e}
        m["exercises_trained"] = len(trained)
        cats = set()
        if trained:
            qs = ",".join("?" * len(trained))
            for r in fetch_all(self.db, f"SELECT DISTINCT category FROM exercises WHERE id IN ({qs})",
                               tuple(trained)):
                cats.add(r["category"])
        m["categories_trained"] = len(cats)
        holds = [float(r["value"]) for r in
                 fetch_all(self.db, "SELECT p.value FROM performances p JOIN exercises e "
                                   "ON e.id=p.exercise_id WHERE e.kind='hold'")]
        m["max_hold"] = max(holds, default=0)
        return m

    def _update_achievements(self, res, base):
        m = dict(base)
        m["level"] = self.level().level
        m["prs"] = fetch_one(self.db, "SELECT COUNT(*) AS n FROM xp_events WHERE category='record'")["n"]
        state = {r["id"]: r for r in fetch_all(self.db, "SELECT * FROM achievements")}
        m["achievements"] = sum(1 for r in state.values() if r["unlocked"])
        today, changed = dt.date.today().isoformat(), False
        for a in AC.ACHIEVEMENTS:
            value = float(m.get(a.metric, 0))
            row = state.get(a.id)
            unlocked = row["unlocked"] if row else None
            if unlocked is None and value >= a.target:
                unlocked, changed = today, True
                res.unlocked.append(a)
                self._award(res, f"ach:{a.id}", a.xp, f"Achievement: {a.name}", "achievement", today)
            self.db.execute("INSERT OR REPLACE INTO achievements(id,progress,unlocked) VALUES(?,?,?)",
                            (a.id, min(value, a.target), unlocked))
        return changed
