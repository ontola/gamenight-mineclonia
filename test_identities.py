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


def player(pid, name, key=None):
    entry = {"id": pid, "name": name}
    if key:
        entry["profile_key"] = key
    return entry


JOEP = "a" * 32
SAM = "b" * 32


class ProfileKeyTests(unittest.TestCase):
    def test_profile_keeps_its_account_on_later_nights(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = accounts(
                root, [seat(0, "night1")], [player("night1", "Joep", JOEP)]
            )
            # A new party: a new player id, the same profile key.
            again = accounts(
                root, [seat(2, "night2")], [player("night2", "Joep", JOEP)]
            )
            self.assertEqual(first[0], again[2])
            guest = accounts(root, [seat(0, "night3")], [player("night3", "Joep")])
            self.assertNotEqual(guest[0], first[0])

    def test_an_account_from_before_profile_keys_is_taken_over(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = accounts(root, [seat(0, "p1")], [player("p1", "Joep")])[0]
            # Same party, the profile key arrives: same account.
            self.assertEqual(
                accounts(root, [seat(0, "p1")], [player("p1", "Joep", JOEP)])[0], old
            )
            registry = json.loads(
                (root / "world/gamenight/identities.json").read_text()
            )["profiles"]
            self.assertNotIn("p1", registry)
            self.assertEqual(registry["profile:" + JOEP], old)

    def test_an_earlier_night_is_claimed_once_by_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            got = accounts(
                root,
                [seat(0, "p1"), seat(1, "p2")],
                [player("p1", "Joep"), player("p2", "Sam")],
            )
            names = root / "world/gamenight/profiles.json"
            names.write_text(
                json.dumps({got[0]: {"name": "Joep"}, got[1]: {"name": "Sam"}})
            )
            later = accounts(root, [seat(1, "n1")], [player("n1", "Joep", JOEP)])
            self.assertEqual(later[1], got[0])
            # Claimed: someone else called Joep later gets a new account.
            other = accounts(root, [seat(0, "n2")], [player("n2", "Joep", SAM)])
            self.assertNotIn(other[0], (got[0], got[1]))

    def test_name_claim_skips_an_account_in_use_or_ambiguous(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            got = accounts(
                root,
                [seat(0, "p1"), seat(1, "p2")],
                [player("p1", "Sam"), player("p2", "Sam")],
            )
            (root / "world/gamenight/profiles.json").write_text(
                json.dumps({got[0]: {"name": "Sam"}, got[1]: {"name": "Sam"}})
            )
            fresh = accounts(root, [seat(0, "n1")], [player("n1", "Sam", SAM)])
            self.assertNotIn(fresh[0], got.values())
