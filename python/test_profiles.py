"""Tests for the local profile slots (no Qt, no network).

Run:  python test_profiles.py
"""
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(tempfile.mkdtemp(prefix="calix5-profiles-"))
os.environ["SKILLTREE_DATA"] = str(ROOT)
os.environ.pop("CALIX_PROFILE", None)

import profile_manager as PM          # noqa: E402  (must follow the env setup)
from database import Store            # noqa: E402
from profile_repo import ProfileRepo  # noqa: E402


class ProfileSlotTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("CALIX_PROFILE", None)
        for slot in range(1, PM.MAX_PROFILES + 1):
            PM.delete_slot(slot)
        for path in (ROOT / PM.ACTIVE_FILE, ROOT / PM.SETTINGS_FILE):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    # ------------------------------------------------------------------ paths
    def test_slot_paths(self):
        self.assertEqual(PM.slot_path(1), ROOT / "progress.db")
        self.assertEqual(PM.slot_path(2), ROOT / "profile-2.db")
        self.assertEqual(PM.slot_path(3), ROOT / "profile-3.db")
        self.assertEqual(PM.MAX_PROFILES, 3)
        for bad in (0, 4, -1, "x", None):
            with self.assertRaises(ValueError):
                PM.slot_path(bad)

    def test_slot_one_keeps_the_original_database(self):
        store = Store()                             # default path == slot 1
        self.addCleanup(store.db.close)
        self.assertEqual(store.path, ROOT / "progress.db")
        ProfileRepo(store.db).create("Legacy")
        self.assertEqual(PM.read_slot(1)["name"], "Legacy")

    # ----------------------------------------------------------- active slot
    def test_active_slot_persists_and_falls_back(self):
        self.assertEqual(PM.get_active_slot(), 1)
        PM.set_active_slot(3)
        self.assertEqual(PM.get_active_slot(), 3)
        (ROOT / PM.ACTIVE_FILE).write_text("not json", encoding="utf-8")
        self.assertEqual(PM.get_active_slot(), 1)
        (ROOT / PM.ACTIVE_FILE).write_text('{"active": 99}', encoding="utf-8")
        self.assertEqual(PM.get_active_slot(), 1)

    def test_resolve_slot_precedence(self):
        PM.set_active_slot(2)
        os.environ["CALIX_PROFILE"] = "3"
        self.assertEqual(PM.resolve_slot(), 3)
        self.assertEqual(PM.resolve_slot("1"), 1)
        self.assertEqual(PM.resolve_slot("bogus"), 3)     # invalid arg falls through to env
        os.environ.pop("CALIX_PROFILE")
        self.assertEqual(PM.resolve_slot(), 2)

    # --------------------------------------------------------------- profiles
    def test_create_switch_and_delete(self):
        self.assertIsNone(PM.read_slot(2))
        self.assertFalse(PM.slot_exists(2))

        store = Store(PM.slot_path(2))
        self.addCleanup(store.db.close)
        ProfileRepo(store.db).create("Bob", "warrior", "#ff922b")

        info = PM.slot_info(2)
        self.assertTrue(info["exists"])
        self.assertEqual(info["name"], "Bob")
        self.assertEqual(info["accent"], "#ff922b")
        self.assertFalse(info["active"])
        self.assertEqual(len(PM.slots()), 3)

        PM.set_active_slot(2)
        self.assertTrue(PM.slot_info(2)["active"])

        backup = Path(str(PM.slot_path(2)) + ".bak-v0")
        backup.write_text("x", encoding="utf-8")
        self.assertTrue(PM.delete_slot(2))
        self.assertFalse(PM.slot_exists(2))
        self.assertFalse(backup.exists())
        self.assertEqual(PM.read_slot(2), None)
        self.assertFalse(PM.delete_slot(2))               # already gone

    def test_progress_is_isolated_between_slots(self):
        one = Store(PM.slot_path(1))
        three = Store(PM.slot_path(3))
        self.addCleanup(one.db.close)
        self.addCleanup(three.db.close)
        one.set_status("pushup", "completed")
        one.add_record("pushup", 20)
        self.assertEqual(three.progress(), {})
        self.assertIsNone(three.best("pushup"))
        self.assertEqual(one.progress()["pushup"], "completed")

    def test_unfinished_or_broken_slot(self):
        # A file that is not a database at all must never be offered as a profile.
        path = PM.slot_path(3)
        path.write_text("not a database", encoding="utf-8")
        self.assertTrue(PM.slot_exists(3))
        self.assertIsNone(PM.read_slot(3))
        self.assertEqual(PM.slot_info(3)["name"], "")
        self.assertTrue(PM.slot_info(3)["exists"])

        # A database without a profile row is a slot that never finished the welcome screen.
        empty = Store(PM.slot_path(2))
        self.addCleanup(empty.db.close)
        self.assertIsNone(PM.read_slot(2))
        self.assertEqual(PM.slot_info(2)["name"], "")

    def test_next_slot_after_delete(self):
        store = Store(PM.slot_path(2))
        self.addCleanup(store.db.close)
        ProfileRepo(store.db).create("Two")
        self.assertEqual(PM.next_slot_after_delete(1), 2)   # another profile exists
        self.assertEqual(PM.next_slot_after_delete(2), 1)   # no other profile -> slot 1

    # --------------------------------------------------------------- settings
    def test_settings_are_shared_by_all_profiles(self):
        from settings import Settings

        first = PM.open_settings_db()
        self.addCleanup(first.close)
        settings = Settings(first)
        settings.set("accent", "#ff6b6b")
        settings.set("music_volume", 12)

        second = PM.open_settings_db()
        self.addCleanup(second.close)
        again = Settings(second)
        self.assertEqual(again.get("accent"), "#ff6b6b")
        self.assertEqual(again.get("music_volume"), 12)
        self.assertEqual(PM.settings_path(), ROOT / "settings.db")


if __name__ == "__main__":
    unittest.main(verbosity=2)
