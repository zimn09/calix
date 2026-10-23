"""Headless tests for everything except the Qt UI.   Run:  python test_logic.py"""
import datetime as dt
import os
import sqlite3
import tempfile
import unittest

import stats
from database import SCHEMA_VERSION, Store
from exercises_data import EXERCISES
from graph import SkillGraph
import ranks as R
from rank_repo import RankRepo
from settings import DEFAULTS, Settings
import progression as P
import achievements as AC
from xp_engine import XpEngine
from scheduling import ScheduleRepo, install_example_routine
from sessions import SessionRepo
from skills_data import SKILLS, SKILLS_BY_ID
from workouts import WorkoutRepo, entry_defaults, estimate_seconds


def fresh():
    d = tempfile.mkdtemp()
    store = Store(os.path.join(d, "t.db"))
    w = WorkoutRepo(store.db)
    return store, w, ScheduleRepo(store.db), SessionRepo(store, w)


def simple_entries(w, ids=("pushup", "plank"), style="strength"):
    out = []
    for i in ids:
        d = entry_defaults(w.exercise(i), style)
        d.update(exercise_id=i, note="n")
        out.append(d)
    return out


class Migration(unittest.TestCase):
    def test_v1_database_is_preserved(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "progress.db")
        db = sqlite3.connect(path)       # exactly what the first release created
        db.execute("CREATE TABLE progress(skill_id TEXT PRIMARY KEY, status TEXT NOT NULL, updated TEXT NOT NULL)")
        db.execute("CREATE TABLE records(id INTEGER PRIMARY KEY AUTOINCREMENT, skill_id TEXT NOT NULL, "
                   "value REAL NOT NULL, logged TEXT NOT NULL)")
        db.execute("INSERT INTO progress VALUES('pushup','completed','2026-01-01T00:00:00')")
        db.execute("INSERT INTO records(skill_id,value,logged) VALUES('pullup',9,'2026-01-02')")
        db.commit()
        db.close()
        s = Store(path)
        self.assertEqual(s.progress(), {"pushup": "completed"})
        self.assertEqual(s.best("pullup"), 9)
        self.assertEqual(s.db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        self.assertTrue(os.path.exists(path + ".bak-v0"))
        tables = {r[0] for r in s.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"exercises", "workouts", "sessions", "session_sets", "schedule_entries"} <= tables)
        Store(path)                       # re-opening is a no-op

    def test_existing_store_features_still_work(self):
        s, *_ = fresh()
        s.set_status("dip", "training")
        s.add_record("dip", 7)
        data = s.export_data()
        s.reset()
        self.assertEqual(s.import_data(data, set(SKILLS_BY_ID)), 1)
        self.assertEqual(s.best("dip"), 7)


class Library(unittest.TestCase):
    def test_library_integrity(self):
        graph = SkillGraph(SKILLS)
        self.assertGreaterEqual(len(EXERCISES), 70)
        self.assertEqual(len({e["id"] for e in EXERCISES}), len(EXERCISES))
        for e in EXERCISES:
            self.assertIn(e["kind"], ("reps", "hold"))
            if e["skill_id"]:
                sk = graph.skills[e["skill_id"]]
                self.assertEqual(sk.unit, "reps" if e["kind"] == "reps" else "s", e["id"])

    def test_filtering(self):
        _, w, *_ = fresh()
        self.assertTrue(all(e["category"] == "pull" for e in w.exercises(category="pull")))
        self.assertTrue(all(e["difficulty"] == 0 for e in w.exercises(difficulty=0)))
        self.assertEqual([e["id"] for e in w.exercises(search="korean")], ["korean_dip"])
        for cat in ("pull", "push", "core", "legs", "skill"):
            self.assertTrue(w.exercises(category=cat))

    def test_custom_exercise(self):
        _, w, *_ = fresh()
        eid = w.add_custom_exercise("Ring Row", "pull", 1, "reps", 3, 8, 60, "rows")
        self.assertEqual(w.exercise(eid)["name"], "Ring Row")
        wid = w.save_workout(None, "X", "", "strength", simple_entries(w, (eid,)))
        self.assertFalse(w.delete_custom_exercise(eid))        # in use
        w.delete_workout(wid)
        self.assertTrue(w.delete_custom_exercise(eid))
        self.assertFalse(w.delete_custom_exercise("pushup"))   # built-ins are protected


class Workouts(unittest.TestCase):
    def test_crud_order_duplicate_delete(self):
        _, w, sched, _ = fresh()
        es = simple_entries(w, ("pushup", "plank", "squat"))
        wid = w.save_workout(None, "  Mine ", "desc", "endurance", es)
        got = w.workout(wid)
        self.assertEqual(got["name"], "Mine")
        self.assertEqual([e["exercise_id"] for e in got["entries"]], ["pushup", "plank", "squat"])
        es = list(reversed(got["entries"]))
        es[0]["note"] = "changed"
        w.save_workout(wid, "Mine", "d2", "skill", es)
        got = w.workout(wid)
        self.assertEqual([e["exercise_id"] for e in got["entries"]], ["squat", "plank", "pushup"])
        self.assertEqual((got["entries"][0]["note"], got["style"]), ("changed", "skill"))
        copy = w.duplicate_workout(wid)
        self.assertEqual(w.workout(copy)["name"], "Mine (copy)")
        self.assertEqual(len(w.workout(copy)["entries"]), 3)
        sched.add_entry("weekly", weekday=1, workout_id=wid)
        w.delete_workout(wid)
        self.assertIsNone(w.workout(wid))
        self.assertEqual(sched.weekly_entries(), [])            # cascade removes schedule entries
        with self.assertRaises(ValueError):
            w.save_workout(None, "  ", "", "strength", es)

    def test_hold_vs_reps_defaults_and_estimate(self):
        _, w, *_ = fresh()
        plank = entry_defaults(w.exercise("plank"), "endurance")
        self.assertEqual((plank["reps"], plank["hold_sec"]), (0, 30))
        push = entry_defaults(w.exercise("pushup"), "strength")
        self.assertEqual((push["sets"], push["reps"], push["hold_sec"]), (5, 5, 0))
        self.assertEqual(entry_defaults(w.exercise("one_arm_pushup"), "endurance")["reps"], 2)
        e = [dict(sets=3, reps=10, hold_sec=0, rest_sets=60, rest_after=90),
             dict(sets=2, reps=0, hold_sec=30, rest_sets=45, rest_after=60)]
        self.assertEqual(estimate_seconds(e), 3 * 30 + 2 * 60 + 90 + 2 * 30 + 45)


class Schedule(unittest.TestCase):
    def setUp(self):
        self.store, self.w, self.s, self.sess = fresh()
        self.wid = self.w.save_workout(None, "A", "", "strength", simple_entries(self.w))

    def test_weekly_once_rest_and_skip(self):
        today = dt.date.today()
        wk = self.s.add_entry("weekly", weekday=today.weekday(), workout_id=self.wid)
        rest = self.s.add_entry("weekly", weekday=(today.weekday() + 1) % 7, is_rest=True)
        once = self.s.add_entry("once", on_date=today + dt.timedelta(days=2), workout_id=self.wid)
        occ = self.s.occurrences(today, today + dt.timedelta(days=14))
        self.assertEqual(sum(1 for d in occ.values() for o in d if o["entry_id"] == wk), 3)
        self.assertTrue(occ[today + dt.timedelta(days=1)][0]["is_rest"])
        self.assertTrue(any(o["entry_id"] == once for o in occ[today + dt.timedelta(days=2)]))
        self.s.skip(wk, today)
        self.assertEqual(self.s.for_date(today), [])
        with self.assertRaises(ValueError):
            self.s.add_entry("weekly", weekday=1)               # neither workout nor rest

    def test_move_remove_edit(self):
        today = dt.date.today()
        wk = self.s.add_entry("weekly", weekday=today.weekday(), workout_id=self.wid)
        occ = self.s.for_date(today)[0]
        tomorrow = today + dt.timedelta(days=1)
        self.s.move_occurrence(occ, tomorrow)                   # weekly -> skip + one-time copy
        self.assertEqual(self.s.for_date(today), [])
        moved = self.s.for_date(tomorrow)[0]
        self.assertEqual(moved["kind"], "once")
        self.s.move_occurrence(moved, today + dt.timedelta(days=3))
        self.assertEqual(len(self.s.for_date(today + dt.timedelta(days=3))), 1)
        self.s.remove_occurrence(self.s.for_date(today + dt.timedelta(days=3))[0])
        self.assertEqual(self.s.for_date(today + dt.timedelta(days=3)), [])
        nxt = today + dt.timedelta(days=7)
        self.s.remove_occurrence(self.s.for_date(nxt)[0], all_weeks=True)
        self.assertEqual(self.s.weekly_entries(), [])
        e = self.s.add_entry("once", on_date=today, workout_id=self.wid)
        self.s.update_entry(e, "weekly", weekday=4, is_rest=True)
        self.assertEqual(self.s.entry(e)["is_rest"], 1)

    def test_example_routine_is_idempotent(self):
        install_example_routine(self.w, self.s)
        install_example_routine(self.w, self.s)
        weekly = self.s.weekly_entries()
        self.assertEqual([(e["weekday"], bool(e["is_rest"])) for e in weekly],
                         [(0, False), (1, False), (2, True), (3, False), (5, False)])
        self.assertEqual(len([x for x in self.w.workouts() if x["name"] == "Push Day"]), 1)


class Sessions(unittest.TestCase):
    def setUp(self):
        self.store, self.w, self.s, self.sess = fresh()
        es = simple_entries(self.w, ("pullup", "plank"))
        es[0].update(sets=3, reps=5, rest_sets=60, rest_after=90)
        es[1].update(sets=2, hold_sec=30, rest_sets=45, rest_after=60)
        self.wid = self.w.save_workout(None, "Pull+Core", "", "strength", es)

    def test_start_resume_finish_and_records(self):
        sid = self.sess.start(self.wid)
        sets = self.sess.sets(sid)
        self.assertEqual(len(sets), 5)
        self.assertEqual([x["rest_sec"] for x in sets], [60, 60, 90, 45, 0])   # last set of workout: no rest
        with self.assertRaises(RuntimeError):
            self.sess.start(self.wid)                                       # one active session at a time
        self.sess.update_set(sets[0]["id"], done=1, reps=8)
        self.sess.update_set(sets[1]["id"], done=1, reps=6)
        self.sess.update_set(sets[3]["id"], done=1, hold=41)
        self.sess.save_state(sid, 123, {"ex_pos": 1})
        # "app restart": a fresh repo sees the same unfinished session
        again = SessionRepo(Store(str(self.store.path)), self.w)
        act = again.active()
        self.assertEqual((act["id"], act["elapsed_sec"]), (sid, 123))
        self.assertEqual(again.load_state(act), {"ex_pos": 1})
        self.assertEqual(sum(x["done"] for x in again.sets(sid)), 3)
        self.assertEqual(stats.totals(self.store.db)["sessions"], 0)        # active sessions don't count
        summ = self.sess.finish(sid, 600)
        self.assertEqual((summ["sets_done"], summ["sets_total"], summ["reps_total"], summ["hold_total"]),
                         (3, 5, 14, 41))
        self.assertEqual(summ["prs"], [])
        self.assertIsNone(self.sess.active())
        # finishing alone must not create records or ranks; only confirmed performance does
        self.assertIsNone(self.store.best("pullup"))
        self.assertEqual(self.sess.best_sets(sid)[0]["value"], 8)

    def test_pr_detection_and_discard(self):
        a = self.sess.start(self.wid)
        self.sess.update_set(self.sess.sets(a)[0]["id"], done=1, reps=6)
        self.sess.finish(a, 100)
        b = self.sess.start(self.wid)
        self.sess.update_set(self.sess.sets(b)[0]["id"], done=1, reps=9)
        summ = self.sess.finish(b, 100)
        self.assertEqual([(p["name"], p["value"], p["previous"]) for p in summ["prs"]], [("Pull-Up", 9, 6)])
        c = self.sess.start(self.wid)
        self.assertIsNone(self.sess.finish(c, 5))                           # nothing done -> discarded
        self.assertIsNone(self.sess.active())
        d = self.sess.start(self.wid)
        self.sess.discard(d)
        self.assertEqual(len(self.sess.history()), 2)

    def test_empty_workout_cannot_start(self):
        e = self.w.save_workout(None, "Empty", "", "strength", [])
        with self.assertRaises(ValueError):
            self.sess.start(e)


class Stats(unittest.TestCase):
    def test_stats_from_saved_data(self):
        store, w, sched, sess = fresh()
        es = simple_entries(w, ("pushup", "plank"))
        es[0].update(sets=2, reps=10)
        es[1].update(sets=1, hold_sec=30)
        wid = w.save_workout(None, "W", "", "strength", es)
        today = dt.date.today()
        for back, reps in ((0, 12), (1, 10), (9, 8)):
            sid = sess.start(wid)
            st = sess.sets(sid)
            sess.update_set(st[0]["id"], done=1, reps=reps)
            if back != 9:
                sess.update_set(st[1]["id"], done=1, reps=reps)
                sess.update_set(st[2]["id"], done=1, hold=35)
            sess.finish(sid, 900)
            day = (today - dt.timedelta(days=back)).isoformat()
            store.db.execute("UPDATE sessions SET session_date=? WHERE id=?", (day, sid))
        store.db.commit()
        t = stats.totals(store.db)
        self.assertEqual((t["sessions"], t["sets"], t["reps"], t["hold"]), (3, 7, 12 + 12 + 10 + 10 + 8, 70))
        dates = stats.session_dates(store.db)
        self.assertEqual(stats.streak(dates, today), 2)
        wc = stats.weekly_counts(dates, today, 4)
        self.assertEqual(sum(n for _, n in wc), 3)
        self.assertEqual(stats.most_performed(store.db)[0]["name"], "Push-Up")
        pr = {r["name"]: r["best"] for r in stats.personal_records(store.db)}
        self.assertEqual(pr, {"Push-Up": 12, "Plank": 35})
        c = stats.completion(store.db)
        self.assertEqual((c["planned"], c["done"], c["full"], c["sessions"]), (9, 7, 2, 3))
        self.assertAlmostEqual(c["pct"], 100 * 7 / 9)
        # adherence: scheduled every weekday of the last 28 days
        for wd in range(7):
            sched.add_entry("weekly", weekday=wd, workout_id=wid)
        store.db.execute("UPDATE schedule_entries SET created=?", ((today - dt.timedelta(days=30)).isoformat(),))
        store.db.commit()
        done, total = stats.adherence(sched, sess, today)
        self.assertEqual(total, 28)
        self.assertEqual(done, 2)       # yesterday and 9 days ago; today excluded from the window


class Ranks(unittest.TestCase):
    def setUp(self):
        self.store, self.w, self.s, self.sess = fresh()
        self.rr = RankRepo(self.store, self.w)

    def test_ladders_are_sane(self):
        lib = {e["id"]: e for e in self.w.exercises()}
        singles = [t for t in self.rr.tracks if t.metric != "line"]
        self.assertEqual({t.exercise_id for t in singles}, {i for i, e in lib.items() if e["builtin"]})
        for t in self.rr.tracks:
            self.assertEqual(len(t.thresholds), R.MAX_RANK, t.id)
            self.assertTrue(all(a < b for a, b in zip(t.thresholds, t.thresholds[1:])), t.id)
        self.assertEqual(len([t for t in self.rr.tracks if t.metric == "line"]), len(R.LINES))
        self.assertEqual({t.group for t in self.rr.tracks}, set(R.GROUPS))

    def test_rank_follows_recorded_performance_per_exercise(self):
        self.assertEqual(self.rr.result_for_exercise("pullup").rank, 0)
        ch = self.rr.log_performance("pullup", 12)
        self.assertEqual([(c["track"], c["before"], c["after"]) for c in ch if c["track_id"] == "pullup"],
                         [("Pull-Up", 0, 4)])
        self.assertEqual(self.rr.result_for_exercise("pullup").rank, 4)       # 12 reps (Warden: >= 11)
        self.assertEqual(self.rr.result_for_exercise("dip").rank, 0)            # independent exercises
        self.assertEqual(self.rr.result_for_exercise("pullup").target, 15)
        self.rr.log_performance("pullup", 5)                                    # a worse set never lowers it
        self.assertEqual(self.rr.result_for_exercise("pullup").rank, 4)
        with self.assertRaises(ValueError):
            self.rr.log_performance("pullup", 0)
        with self.assertRaises(ValueError):
            self.rr.log_performance("nonexistent", 5)

    def test_metrics_differ_reps_hold_and_line(self):
        self.assertEqual(self.rr.by_exercise["pullup"].unit, "reps")
        self.assertEqual(self.rr.by_exercise["l_sit"].unit, "s")
        self.rr.log_performance("l_sit", 20)                                    # 20 s: >= 18 (rank 3)
        self.assertEqual(self.rr.result_for_exercise("l_sit").rank, 3)
        self.rr.log_performance("tuck_planche", 6)
        line = self.rr.evaluate_all()["line_planche"]
        self.assertEqual(line.headline, "Mastered: Tuck Planche  (2/5 steps)")   # tuck >= 5 s mastered
        self.assertIn("Advanced Tuck Planche", line.goal)
        self.assertGreater(line.rank, 0)
        self.rr.log_performance("adv_tuck_planche", 5)
        self.assertGreater(self.rr.evaluate_all()["line_planche"].best, line.best)

    def test_completed_skill_counts_for_lines_but_not_singles(self):
        self.store.set_status("tuck_planche", "completed")
        res = self.rr.evaluate_all()
        self.assertGreater(res["line_planche"].rank, 0)
        self.assertEqual(res["tuck_planche"].rank, 0)

    def test_tree_record_feeds_rank_and_history_is_derived(self):
        self.store.add_record("pullup", 9)
        self.assertEqual(self.rr.result_for_exercise("pullup").rank, 3)
        self.rr.log_performance("pullup", 20, day=dt.date.today() + dt.timedelta(days=1))
        r = self.rr.result_for_exercise("pullup")
        self.assertEqual(r.rank, 6)
        self.assertEqual(r.history[0].rank, 3)           # first logged value jumped straight to Vanguard
        self.assertEqual((r.history[-1].rank, r.history[-1].value), (6, 20))
        pid = self.rr.performances("pullup")[0]["id"]
        self.rr.delete_performance(pid)                  # deleting recalculates everything
        self.assertEqual(self.rr.result_for_exercise("pullup").rank, 3)

    def test_workout_does_not_raise_rank_until_confirmed(self):
        es = simple_entries(self.w, ("pullup",))
        es[0].update(sets=2, reps=8)
        wid = self.w.save_workout(None, "P", "", "strength", es)
        sid = self.sess.start(wid)
        for s in self.sess.sets(sid):
            self.sess.update_set(s["id"], done=1)
        self.sess.finish(sid, 60)
        self.assertEqual(self.rr.result_for_exercise("pullup").rank, 0)         # finishing is not enough
        best = self.sess.best_sets(sid)
        self.assertEqual([(b["exercise_id"], b["value"]) for b in best], [("pullup", 8)])
        changes = self.rr.record_session(sid, [dict(exercise_id="pullup", set_id=best[0]["set_id"], value=7)])
        self.assertEqual(self.rr.result_for_exercise("pullup").best, 7)          # user-corrected real value
        self.assertTrue(any(c["track_id"] == "pullup" and c["up"] for c in changes))
        self.assertEqual(self.store.best("pullup"), 7)                           # skill-tree record synced
        row = self.store.db.execute("SELECT reps, confirmed FROM session_sets WHERE id=?", (best[0]["set_id"],)).fetchone()
        self.assertEqual(tuple(row), (7, 1))
        self.sess.delete_session(sid)                                            # cascade removes the performance
        self.assertEqual(len(self.rr.performances("pullup")), 0)

    def test_import_history_is_explicit_and_idempotent(self):
        es = simple_entries(self.w, ("squat",))
        wid = self.w.save_workout(None, "S", "", "strength", es)
        sid = self.sess.start(wid)
        self.sess.update_set(self.sess.sets(sid)[0]["id"], done=1, reps=30)
        self.sess.finish(sid, 60)
        self.assertEqual(self.rr.result_for_exercise("squat").rank, 0)
        self.assertEqual(self.rr.import_history(), 1)
        self.assertEqual(self.rr.import_history(), 0)
        self.assertEqual(self.rr.result_for_exercise("squat").best, 30)

    def test_overview_helpers(self):
        self.rr.log_performance("pullup", 12)
        self.rr.log_performance("plank", 20)
        res = self.rr.results()
        top = R.strongest(res, 2)
        self.assertEqual(top[0].track.id, "pullup")
        scores = R.group_scores(res)
        self.assertGreater(scores["pulling"], scores["legs"])
        rec = R.recommend(res, 3)
        self.assertEqual(len(rec), 3)
        self.assertTrue(rec[0][0].practiced)


class SettingsTests(unittest.TestCase):
    def test_defaults_persist_validate_reset(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "s.db")
        st = Store(path)
        s = Settings(st.db)
        self.assertEqual(s.all(), DEFAULTS)
        seen = []
        s.subscribe(lambda cfg: seen.append(cfg["accent"]))
        s.set("accent", "#9775FA")
        s.set("bg", "black")
        s.set("animations", False)
        self.assertEqual(seen, ["#9775fa", "#9775fa", "#9775fa"])
        for key, bad in (("bg", "neon"), ("accent", "blue"), ("animations", "yes"), ("font_size", 40)):
            with self.assertRaises(ValueError):
                s.set(key, bad)
        with self.assertRaises(KeyError):
            s.set("nope", 1)
        s2 = Settings(Store(path).db)                      # "next launch"
        self.assertEqual((s2["accent"], s2["bg"], s2["animations"]), ("#9775fa", "black", False))
        s2.reset()
        self.assertEqual(Settings(Store(path).db).all(), DEFAULTS)

    def test_theme_is_built_from_settings(self):
        import theme
        base = theme.build_qss(DEFAULTS)
        self.assertIn("#4dabf7", base)
        cfg = dict(DEFAULTS, accent="#ff6b6b", bg="black", corners="sharp", font_size=12, animations=False)
        css = theme.build_qss(cfg)
        self.assertIn("#ff6b6b", css)
        self.assertNotIn("#4dabf7", css)
        self.assertIn("#000000", css)
        self.assertIn("font-size: 12pt", css)
        self.assertNotIn("border-radius: 12px", css)
        self.assertIn("qlineargradient", theme.build_qss(dict(DEFAULTS, bg="gradient")))
        self.assertIn("url(/tmp/x.png)", theme.build_qss(dict(DEFAULTS, bg="pattern"), "/tmp/x.png"))


class MigrationV2(unittest.TestCase):
    def test_v2_database_keeps_workouts_and_sessions(self):
        store, w, s, sess = fresh()
        wid = w.save_workout(None, "Keep me", "", "strength", simple_entries(w))
        sid = sess.start(wid)
        sess.update_set(sess.sets(sid)[0]["id"], done=1)
        sess.finish(sid, 60)
        path = str(store.path)
        store.db.execute("DROP TABLE settings")
        store.db.execute("DROP TABLE performances")
        store.db.execute("PRAGMA user_version=2")
        store.db.commit()
        again = Store(path)                                # re-runs migration 3 only
        self.assertTrue(os.path.exists(path + ".bak-v2"))
        self.assertEqual(WorkoutRepo(again.db).workout(wid)["name"], "Keep me")
        self.assertEqual(len(SessionRepo(again, WorkoutRepo(again.db)).history()), 1)
        self.assertEqual(again.db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)


def engine(path_or_none=None):
    """Fresh app stack with an XP engine."""
    if path_or_none:
        store = Store(path_or_none)
        w = WorkoutRepo(store.db)
        sched, sess = ScheduleRepo(store.db), SessionRepo(store, w)
    else:
        store, w, sched, sess = fresh()
    rr = RankRepo(store, w)
    return store, w, sess, rr, XpEngine(store, w, sess, rr, SkillGraph(SKILLS))


def do_workout(w, sess, day=None, elapsed=600, entry_id=None, done_share=1.0, name="W", ids=("pushup", "plank")):
    wid = next((x["id"] for x in w.workouts() if x["name"] == name), None) or \
        w.save_workout(None, name, "", "strength", simple_entries(w, ids))
    sid = sess.start(wid, entry_id)
    sets = sess.sets(sid)
    for s in sets[:max(1, round(len(sets) * done_share))]:
        sess.update_set(s["id"], done=1)
    sess.finish(sid, elapsed)
    if day:
        sess.db.execute("UPDATE sessions SET session_date=? WHERE id=?", (day.isoformat(), sid))
        sess.db.commit()
    return sid


class LevelCurve(unittest.TestCase):
    def test_curve_and_titles(self):
        self.assertEqual(P.level_info(0).level, 1)
        self.assertEqual(P.xp_needed(1), 100)
        run = 0
        for n in range(1, 60):
            self.assertEqual(P.cumulative(n), run)
            run += P.xp_needed(n)
        needs = [P.xp_needed(n) for n in range(1, 60)]
        self.assertTrue(all(a < b for a, b in zip(needs, needs[1:])))        # every level costs more
        for n in range(2, 40):
            self.assertEqual(P.level_info(P.cumulative(n)).level, n)         # exactly on the boundary
            self.assertEqual(P.level_info(P.cumulative(n) - 1).level, n - 1)  # one XP short
        info = P.level_info(P.cumulative(3) + 50)
        self.assertEqual((info.level, info.into, info.need), (3, 50, P.xp_needed(3)))
        self.assertAlmostEqual(info.progress, 50 / P.xp_needed(3))
        self.assertEqual([P.title_for(n)[0] for n in (1, 4, 5, 10, 20, 30, 60)],
                         ["Beginner", "Beginner", "Apprentice", "Warrior", "Elite", "Master", "Legend"])
        self.assertEqual(P.level_info(P.cumulative(P.MAX_LEVEL) + 999).progress, 1.0)

    def test_achievement_catalogue(self):
        self.assertGreaterEqual(len(AC.ACHIEVEMENTS), 70)
        self.assertEqual({a.category for a in AC.ACHIEVEMENTS}, set(AC.CATEGORY_LABELS))
        self.assertEqual({a.rarity for a in AC.ACHIEVEMENTS}, set(AC.RARITIES))
        rank = {k: v[2] for k, v in AC.RARITIES.items()}
        by = {}
        for a in AC.ACHIEVEMENTS:
            by.setdefault(a.rarity, []).append(a.xp)
        self.assertLess(max(by["common"]), max(by["legendary"]))
        self.assertLess(sum(by["common"]) / len(by["common"]), sum(by["legendary"]) / len(by["legendary"]))
        graph = SkillGraph(SKILLS)
        for a in AC.ACHIEVEMENTS:
            self.assertGreater(a.xp, 0)
            self.assertTrue(all(s in graph.skills for s in a.skills), a.id)


class XpTests(unittest.TestCase):
    def setUp(self):
        self.store, self.w, self.sess, self.rr, self.xp = engine()

    def by_cat(self, res):
        out = {}
        for a in res.awards:
            out[a["category"]] = out.get(a["category"], 0) + a["amount"]
        return out

    def test_opening_the_app_or_building_workouts_gives_nothing(self):
        self.w.save_workout(None, "Just built", "", "strength", simple_entries(self.w))
        self.store.set_status("pushup", "training")                       # "training" is not an achievement
        res = self.xp.sync()
        self.assertTrue(res.empty)
        self.assertEqual(self.xp.total_xp(), 0)
        self.assertEqual(self.xp.level().level, 1)

    def test_workout_pays_once_and_never_again(self):
        do_workout(self.w, self.sess)
        res = self.xp.sync()
        cats = self.by_cat(res)
        self.assertEqual(cats["workout"], P.XP_WORKOUT)
        self.assertEqual(cats["set"], 10 * P.XP_PER_SET + 2 * P.XP_PER_EXERCISE)   # 10 sets, 2 full exercises
        total = self.xp.total_xp()
        for _ in range(3):                                                  # reopening / re-reading changes nothing
            self.assertTrue(self.xp.sync().empty)
        self.assertEqual(self.xp.total_xp(), total)

    def test_fake_or_tiny_workouts_pay_nothing(self):
        do_workout(self.w, self.sess, elapsed=30)                           # under 2 minutes
        do_workout(self.w, self.sess, done_share=0.1)                       # only a tenth of the sets
        self.assertEqual(self.by_cat(self.xp.sync()).get("workout", 0), 0)
        self.assertEqual(self.xp.total_xp(), 0)

    def test_daily_cap_blocks_farming(self):
        for _ in range(5):
            do_workout(self.w, self.sess)
        res = self.xp.sync()
        self.assertEqual(len([a for a in res.awards if a["category"] == "workout"]), P.SESSION_DAILY_CAP)
        self.assertTrue(self.xp.sync().empty)
        do_workout(self.w, self.sess, day=dt.date.today() - dt.timedelta(days=1))   # another day pays again
        self.assertEqual(len([a for a in self.xp.sync().awards if a["category"] == "workout"]), 1)

    def test_scheduled_bonus(self):
        do_workout(self.w, self.sess, entry_id=1)
        res = self.xp.sync()
        self.assertTrue(any(a["reason"].startswith("Scheduled workout") and a["amount"] == P.XP_SCHEDULED
                            for a in res.awards))

    def test_records_and_ranks_pay_once(self):
        today = dt.date.today()
        self.rr.log_performance("pullup", 8, day=today - dt.timedelta(days=2))
        res = self.xp.sync()
        keys = {r[0] for r in self.xp.db.execute("SELECT key FROM xp_events")}
        self.assertIn("rank:pullup:3", keys)
        self.assertFalse(any(k.startswith("pr:") for k in keys))             # first ever value is not a record
        self.rr.log_performance("pullup", 10, day=today - dt.timedelta(days=1))
        res = self.xp.sync()
        pr = [a for a in res.awards if a["category"] == "record"]
        self.assertEqual([a["amount"] for a in pr], [P.XP_PR[1]])
        self.rr.log_performance("pullup", 11, day=today - dt.timedelta(days=1))   # same day: no 2nd record XP
        res = self.xp.sync()
        self.assertFalse([a for a in res.awards if a["category"] == "record"])
        self.assertTrue([a for a in res.awards if a["category"] == "rank"])        # but Warden is a new rank
        self.rr.log_performance("pullup", 6)                                       # worse: nothing
        self.assertTrue(self.xp.sync().empty)
        with self.assertRaises(ValueError):
            self.rr.log_performance("pullup", 999)                                 # absurd value is rejected

    def test_skill_xp_has_no_loopholes(self):
        self.assertTrue(self.xp.sync().empty)                                      # root skills are not "unlocked"
        self.store.set_status("wall_pushup", "completed")
        res = self.xp.sync()
        self.assertEqual(self.by_cat(res)["skill"], P.XP_SKILL_DONE[0] + P.XP_SKILL_UNLOCK[0])   # done + unlocked child
        self.store.set_status("wall_pushup", None)                                  # un-complete and complete again
        self.store.set_status("wall_pushup", "completed")
        self.assertEqual(self.by_cat(self.xp.sync()).get("skill", 0), 0)
        self.assertGreater(self.xp.total_xp(), 0)                                   # XP is never taken back

    def test_achievements_progress_unlock_and_reward(self):
        self.assertTrue(all(r["unlocked"] is None and r["progress"] == 0 for r in self.xp.achievement_rows()))
        do_workout(self.w, self.sess)
        res = self.xp.sync()
        self.assertIn("workouts_1", [a.id for a in res.unlocked])
        rows = {r["a"].id: r for r in self.xp.achievement_rows()}
        self.assertEqual(rows["workouts_1"]["unlocked"], dt.date.today().isoformat())
        self.assertEqual((rows["workouts_10"]["progress"], rows["workouts_10"]["unlocked"]), (1.0, None))
        self.assertAlmostEqual(rows["workouts_10"]["pct"], 0.1)
        ledger = self.xp.db.execute("SELECT amount FROM xp_events WHERE key='ach:workouts_1'").fetchall()
        self.assertEqual(ledger, [(AC.BY_ID["workouts_1"].xp,)])
        self.rr.log_performance("pullup", 5)
        self.assertIn("pullup_5", [a.id for a in self.xp.sync().unlocked])
        self.assertTrue(self.xp.sync().empty)                                        # nothing unlocks twice
        self.assertIn("pullup_5", [r["a"].id for r in self.xp.achievements_for_skill("pullup")])
        self.assertTrue(all(r["unlocked"] is None for r in self.xp.nearest(3)))

    def test_level_up_and_persistence_after_restart(self):
        do_workout(self.w, self.sess)
        do_workout(self.w, self.sess, day=dt.date.today() - dt.timedelta(days=1))
        res = self.xp.sync()
        self.assertTrue(res.leveled_up)
        self.assertEqual((res.level_before.level, res.level_after.level), (1, 2))
        self.assertEqual(res.level_after.title, "Beginner")
        total, unlocked = self.xp.total_xp(), [r["a"].id for r in self.xp.achievement_rows() if r["unlocked"]]
        # "restart": new connection, new objects
        store2, w2, sess2, rr2, xp2 = engine(str(self.store.path))
        self.assertEqual(xp2.total_xp(), total)
        self.assertEqual([r["a"].id for r in xp2.achievement_rows() if r["unlocked"]], unlocked)
        self.assertTrue(xp2.sync().empty)                                            # no duplicates after restart
        self.assertEqual(xp2.total_xp(), total)
        st = store2.db.execute("SELECT total_xp, level, title FROM xp_state").fetchone()
        self.assertEqual(st, (total, 2, "Beginner"))
        hist = xp2.history()
        self.assertEqual(sum(h["amount"] for h in hist), total)
        self.assertEqual({h["category"] for h in xp2.history("workout")}, {"workout"})

    def test_existing_data_is_credited_on_first_sync_only(self):
        """History recorded before the XP system existed counts (it is real), exactly once."""
        do_workout(self.w, self.sess, day=dt.date.today() - dt.timedelta(days=3))
        self.rr.log_performance("squat", 30, day=dt.date.today() - dt.timedelta(days=2))
        first = self.xp.sync()
        self.assertTrue(first.awards)
        self.assertEqual(sorted({a["earned_on"] for a in first.awards if a["category"] != "achievement"}),
                         sorted({(dt.date.today() - dt.timedelta(days=d)).isoformat() for d in (3, 2)}))
        self.assertTrue(self.xp.sync().empty)

    def test_consistency_metrics(self):
        today = dt.date.today()
        for d in range(3):
            do_workout(self.w, self.sess, day=today - dt.timedelta(days=d))
        m = self.xp._base_metrics()
        self.assertEqual((m["workouts"], m["streak_days"]), (3, 3))
        self.assertGreaterEqual(m["week_best"], 1)


class MigrationV3(unittest.TestCase):
    def test_v3_database_keeps_everything(self):
        store, w, s, sess = fresh()
        wid = w.save_workout(None, "Keep", "", "strength", simple_entries(w))
        store.set_status("pushup", "completed")
        rr = RankRepo(store, w)
        rr.log_performance("pullup", 9)
        path = str(store.path)
        for tbl in ("xp_events", "xp_state", "achievements"):
            store.db.execute(f"DROP TABLE {tbl}")
        store.db.execute("PRAGMA user_version=3")
        store.db.commit()
        again = Store(path)
        self.assertTrue(os.path.exists(path + ".bak-v3"))
        self.assertEqual(again.progress(), {"pushup": "completed"})
        self.assertEqual(WorkoutRepo(again.db).workout(wid)["name"], "Keep")
        self.assertEqual(len(again.db.execute("SELECT * FROM performances").fetchall()), 1)
        self.assertEqual(again.db.execute("SELECT COUNT(*) FROM xp_events").fetchone()[0], 0)
        self.assertEqual(again.db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main(verbosity=1)
