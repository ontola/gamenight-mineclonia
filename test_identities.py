import json
from pathlib import Path
import tempfile
import unittest
from identities import accounts


def seat(index, profile):
    return {"index": index, "occupant": {"kind": "local", "player_id": profile}}


class IdentityTests(unittest.TestCase):
    def test_legacy_ownership_follows_profile_after_seat_shuffle_and_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            world = root / "world"
            world.mkdir()
            legacy = world / "players.sqlite"
            legacy.write_bytes(b"existing inventory, positions and mod keys")
            self.assertEqual(
                accounts(root, [seat(0, "alex"), seat(2, "bo")]),
                {0: "Couch1", 2: "Couch3"},
            )
            self.assertEqual(
                accounts(root, [seat(3, "alex"), seat(0, "bo")]),
                {3: "Couch1", 0: "Couch3"},
            )
            self.assertEqual(
                legacy.read_bytes(), b"existing inventory, positions and mod keys"
            )
            newcomer = accounts(root, [seat(0, "cleo")])[0]
            self.assertTrue(newcomer.startswith("GN_"))
            self.assertLessEqual(len(newcomer), 19)
            self.assertEqual(accounts(root, [seat(1, "cleo")])[1], newcomer)
            self.assertEqual(accounts(root, [seat(0, "alex")])[0], "Couch1")

    def test_empty_preparation_does_not_claim_a_saved_account(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(
                accounts(root, [{"index": 0, "occupant": {"kind": "empty"}}]),
                {0: "Preview"},
            )
            self.assertFalse((root / "world/gamenight/identities.json").exists())

    def test_invalid_or_duplicate_profiles_leave_registry_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            accounts(root, [seat(0, "alex")])
            path = root / "world/gamenight/identities.json"
            before = path.read_bytes()
            for seats in ([seat(0, "alex"), seat(1, "alex")], [seat(0, None)]):
                with self.assertRaises(ValueError):
                    accounts(root, seats)
                self.assertEqual(path.read_bytes(), before)

    def test_corrupt_ownership_is_not_reset_or_reassigned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            accounts(root, [seat(0, "alex")])
            path = root / "world/gamenight/identities.json"
            path.write_text(
                json.dumps(
                    {"version": 1, "profiles": {"alex": "Couch1", "bo": "Couch1"}}
                )
            )
            with self.assertRaises(ValueError):
                accounts(root, [seat(0, "cleo")])
