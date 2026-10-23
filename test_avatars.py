"""Tests for cross-profile avatar unlocks (no Qt, no network).

Run:  python test_avatars.py
"""
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(tempfile.mkdtemp(prefix="calix51-avatars-"))
os.environ["SKILLTREE_DATA"] = str(ROOT)
os.environ.pop("CALIX_PROFILE", None)

import achievements as AC           # noqa: E402
import avatar_data as AD            # noqa: E402
import avatar_unlocks as AU         # noqa: E402
import profile_manager as PM        # noqa: E402
from database import Store          # noqa: E402
from profile_repo import ProfileRepo  # noqa: E402


class AvatarUnlockTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("CALIX_PROFILE", None)
        for slot in range(1, PM.MAX_PROFILES + 1):
            PM.delete_slot(slot)
        for name in (PM.UNLOCKS_FILE, PM.ACTIVE_FILE, PM.SETTINGS_FILE):
            try:
                (ROOT / name).unlink()
            except FileNotFoundError:
                pass

    # ------------------------------------------------------------- catalogue
    def test_every_avatar_is_tied_to_a_real_achievement(self):
        self.assertEqual(AD.DEFAULT_AVATAR, "warrior")
        self.assertFalse(AD.AVATAR_BY_ID["warrior"].get("unlock"))
        for avatar in AD.AVATARS:
            unlock = avatar.get("unlock")
            if avatar["id"] == "warrior":
                continue
            self.assertEqual(unlock["type"], "achievement", avatar["id"])
            self.assertIn(unlock["id"], AC.BY_ID, avatar["id"])
            self.assertTrue(AD.avatar_requirement(avatar))

    def test_first_push_and_pull_up_unlock_avatars(self):
        self.assertIn("pushup_1", AC.BY_ID)
        self.assertIn("pullup_1", AC.BY_ID)
        self.assertEqual(AD.unlocked_by_achievements({"pushup_1"}), ["monk"])
        self.assertEqual(AD.unlocked_by_achievements({"pullup_1"}), ["nomad"])
        self.assertEqual(AD.unlocked_by_achievements(set()), [])

    # ------------------------------------------------------------ shared db
    def test_unlocks_are_shared_and_idempotent(self):
        db = PM.open_unlocks_db()
        self.addCleanup(db.close)
        ids = AU.unlocked_ids(db)
        self.assertIn("warrior", ids)                 # free avatar is always available
        self.assertNotIn("monk", ids)

        new = AU.unlock(db, ["monk"], "test")
        self.assertEqual([a["id"] for a in new], ["monk"])
        self.assertEqual(AU.unlock(db, ["monk"], "test"), [])
        self.assertIn("monk", AU.unlocked_ids(db))

    def test_scan_takes_achievements_from_any_profile(self):
        one = Store(PM.slot_path(1))
        self.addCleanup(one.db.close)
        ProfileRepo(one.db).create("One", "warrior")
        one.db.execute("INSERT OR REPLACE INTO achievements(id,progress,unlocked) "
                       "VALUES('pushup_1',1,'2026-01-01')")
        one.db.commit()

        # An avatar equipped before the lock system existed is grandfathered.
        two = Store(PM.slot_path(2))
        self.addCleanup(two.db.close)
        ProfileRepo(two.db).create("Two", "sage")

        db = PM.open_unlocks_db()
        self.addCleanup(db.close)
        new = AU.scan_profiles(db, [PM.slot_path(1), PM.slot_path(2)])
        self.assertEqual({a["id"] for a in new}, {"monk", "sage"})
        self.assertTrue({"warrior", "monk", "sage"} <= AU.unlocked_ids(db))

        # Unlocks live in the shared file, so deleting the profile keeps them.
        one.db.close()
        PM.delete_slot(1)
        self.assertIn("monk", AU.unlocked_ids(db))

    def test_missing_slot_is_ignored(self):
        db = PM.open_unlocks_db()
        self.addCleanup(db.close)
        self.assertEqual(AU.scan_profiles(db, [PM.slot_path(3)]), [])
        self.assertEqual(AU.unlocked_ids(db), {"warrior"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
