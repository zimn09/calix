"""Headless tests for the local coach (no Qt, no model).   Run:  python test_assistant.py"""
import os
import tempfile
import unittest

from assistant import Coach, detect_run_entities, normalize, parse_sets_reps, parse_window
from database import Store
from graph import SkillGraph
from skills_data import SKILLS
from workouts import WorkoutRepo


def fresh_coach():
    d = tempfile.mkdtemp()
    store = Store(os.path.join(d, "t.db"))
    w = WorkoutRepo(store.db)
    return Coach(store, w, graph=SkillGraph(SKILLS)), store, w


def add_completed_sets(store, items, day="2026-11-03"):
    """items = [(exercise_id, name, kind, reps, hold)] in one finished session."""
    cur = store.db.execute(
        "INSERT INTO sessions(workout_name,session_date,started,status,elapsed_sec,state_json)"
        " VALUES('Test',?,?,'completed',600,'{}')", (day, day + "T10:00:00"))
    sid = cur.lastrowid
    for pos, (ex_id, name, kind, reps, hold) in enumerate(items):
        store.db.execute(
            "INSERT INTO session_sets(session_id,ex_pos,set_idx,exercise_id,exercise_name,kind,"
            "target_reps,target_hold,reps,hold,rest_sec,done) VALUES(?,?,0,?,?,?,?,?,?,?,60,1)",
            (sid, pos, ex_id, name, kind, reps, hold, reps, hold))
    store.db.commit()
    return sid


class Parsing(unittest.TestCase):
    def test_normalize_strips_diacritics_and_case(self):
        self.assertEqual(normalize("Dřepy 3×10!"), "drepy 3 10")

    def test_sets_and_reps(self):
        self.assertEqual(parse_sets_reps(["3x12"], "did 3x12 push ups"), (3, 12, 0))
        self.assertEqual(parse_sets_reps([], "3 sets of 8 rows"), (3, 8, 0))
        self.assertEqual(parse_sets_reps([], "4 x 6 pull ups"), (4, 6, 0))

    def test_holds(self):
        self.assertEqual(parse_sets_reps([], "plank 1:30")[2], 90)
        self.assertEqual(parse_sets_reps([], "plank 90 s")[2], 90)

    def test_run_entities(self):
        self.assertEqual(detect_run_entities("ran 5k in 26:30", []), (5000.0, 1590))
        self.assertEqual(detect_run_entities("ran 3.2 km in 20 min", []), (3200.0, 1200))

    def test_time_windows(self):
        self.assertEqual(parse_window("what did I do today")[1], "today")
        self.assertEqual(parse_window("sum of reps this week")[1], "this week")
        self.assertEqual(parse_window("everything ever")[1], "all time")


class SmallTalk(unittest.TestCase):
    def setUp(self):
        self.coach, self.store, self.wrepo = fresh_coach()

    def test_greetings_answer(self):
        for text in ["hey", "Hey!", "hi", "ahoj", "čau", "sup"]:
            r = self.coach.handle(text)
            self.assertEqual(r.intent, "greet", text)
            self.assertTrue(r.text)

    def test_greeting_before_a_question_is_ignored(self):
        r = self.coach.handle("hey, what's my best pull up?")
        self.assertEqual(r.intent, "query_best")

    def test_small_talk(self):
        for text, intent in [("thanks", "thanks"), ("diky", "thanks"),
                             ("who are you?", "identity"), ("how are you?", "mood"),
                             ("see you", "bye")]:
            self.assertEqual(self.coach.handle(text).intent, intent, text)

    def test_unknown_text_gets_guidance_not_silence(self):
        r = self.coach.handle("banana rocket")
        self.assertTrue(r.text)
        self.assertEqual(r.intent, "unknown")

    def test_trained_today(self):
        self.assertIn("Not yet", self.coach.handle("did I train today?").text)
        add_completed_sets(self.store, [("pushup", "Push-Up", "reps", 10, 0)],
                           day=__import__("datetime").date.today().isoformat())
        self.assertIn("Yes", self.coach.handle("did I train today?").text)

    def test_last_session(self):
        add_completed_sets(self.store, [("plank", "Plank", "hold", 0, 45)])
        self.assertIn("Plank", self.coach.handle("what did I do last time?").text)


class Understanding(unittest.TestCase):
    def setUp(self):
        self.coach, self.store, self.wrepo = fresh_coach()

    def test_names_a_push_up(self):
        r = self.coach.handle("did 3x12 push ups")
        self.assertEqual(r.intent, "log_set")
        self.assertEqual(len(r.actions), 1)
        a = r.actions[0]
        self.assertEqual(a.exercise_name, "Push-Up")
        self.assertEqual((a.sets, a.reps), (3, 12))

    def test_typos_and_slang(self):
        for text, expected in [("pushups 2x20", "Push-Up"),
                               ("shyby 3x5", "Pull-Up"),
                               ("dřepy 3x10", "Bodyweight Squat"),
                               ("plank 1:30", "Plank")]:
            r = self.coach.handle(text)
            self.assertTrue(r.actions, text)
            self.assertEqual(r.actions[0].exercise_name, expected, text)

    def test_run_is_detected(self):
        r = self.coach.handle("ran 5 km in 26:30")
        self.assertEqual(r.intent, "log_run")
        self.assertEqual(r.actions[0].distance_m, 5000)
        self.assertEqual(r.actions[0].seconds, 1590)

    def test_unknown_exercise_is_answered_not_guessed(self):
        r = self.coach.handle("did 3x12 flurbo jumps")
        self.assertFalse(r.actions)
        self.assertIn("couldn't tell", r.text)

    def test_apply_writes_performance_and_record(self):
        r = self.coach.handle("did 3x12 push ups")
        self.coach.apply(r.actions[0])
        self.assertEqual(self.store.best("pushup"), 12)
        row = self.store.db.execute(
            "SELECT value, source FROM performances WHERE exercise_id='pushup'").fetchone()
        self.assertEqual(row[0], 12)
        self.assertEqual(row[1], "coach")
        # the set is part of a real session, so History and the totals see it
        sets = self.store.db.execute(
            "SELECT COUNT(*), MAX(session_id) FROM session_sets WHERE exercise_id='pushup' AND done=1"
        ).fetchone()
        self.assertEqual(sets[0], 3)
        name = self.store.db.execute("SELECT workout_name FROM sessions WHERE id=?",
                                    (sets[1],)).fetchone()[0]
        self.assertEqual(name, "Coach log")
        self.assertIn("36 reps", self.coach.handle("sum of reps today").text)

    def test_totals_answer_from_database(self):
        add_completed_sets(self.store, [("pushup", "Push-Up", "reps", 12, 0),
                                        ("pushup", "Push-Up", "reps", 10, 0),
                                        ("plank", "Plank", "hold", 0, 60)])
        r = self.coach.handle("sum of reps")
        self.assertIn("22 reps", r.text)
        r2 = self.coach.handle("how many push ups in total")
        self.assertIn("22 reps", r2.text)

    def test_best_answer(self):
        add_completed_sets(self.store, [("pullup", "Pull-Up", "reps", 9, 0)])
        r = self.coach.handle("what's my best pull up?")
        self.assertEqual(r.intent, "query_best")
        self.assertIn("9", r.text)

    def test_progress_and_suggestion(self):
        r = self.coach.handle("how am i doing?")
        self.assertIn("skills completed", r.text)
        s = self.coach.handle("what should I train today?")
        self.assertEqual(s.intent, "suggest")
        self.assertTrue(s.entities)

    def test_explain_uses_catalogue(self):
        r = self.coach.handle("what is a muscle up?")
        self.assertEqual(r.intent, "explain")
        self.assertIn("Muscle-Up", r.text)

    def test_help_lists_abilities(self):
        r = self.coach.handle("help")
        self.assertIn("3x12 push ups", r.text)

    def test_empty_input_is_handled(self):
        r = self.coach.handle("   ")
        self.assertEqual(r.intent, "help")


if __name__ == "__main__":
    unittest.main(verbosity=2)
