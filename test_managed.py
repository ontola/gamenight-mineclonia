import unittest
from unittest import mock
from managed import routed, Adapter


class Routing(unittest.TestCase):
    def test_superseded_notifications_do_not_close_world(self):
        adapter = Adapter.__new__(Adapter)
        adapter.receive({"type": "error", "message": "stale participation session"})
        adapter.receive(
            {"type": "error", "message": "ready for unknown or non-preparing session"}
        )
        with self.assertRaises(RuntimeError):
            adapter.receive({"type": "error", "message": "invalid launch token"})

    def test_rename_updates_appearance_without_reprepare(self):
        adapter = Adapter.__new__(Adapter)
        seat = {
            "index": 0,
            "controller": "ordinal:0",
            "occupant": {"kind": "local", "player_id": "a"},
        }
        adapter.session, adapter.seats, adapter.root = "s1", [seat], None
        adapter.players = [{"id": "a", "name": "Rocket"}]
        adapter.prepare = {
            "type": "prepare",
            "session": "s1",
            "seats": [seat],
            "players": adapter.players,
        }
        adapter.accounts = ["Couch1"]
        with mock.patch("managed.profiles.publish") as publish:
            adapter.receive(
                {
                    "type": "players_updated",
                    "session": "s1",
                    "players": [{"id": "a", "name": "Joep", "avatar": "face"}],
                }
            )
        self.assertEqual(adapter.session, "s1")
        self.assertEqual(adapter.players[0]["name"], "Joep")
        publish.assert_called_once()
        self.assertEqual(publish.call_args.args[2][0]["avatar"], "face")

    def seat(self, token, kind="local"):
        return {"controller": token, "occupant": {"kind": kind}}

    def pad(self, token, buttons=1):
        return {"controller": token, "buttons": buttons, "axes": [1, 2, 3, 4, 5, 6]}

    def test_token_mapping_not_device_order(self):
        result = routed(
            [self.seat("b"), self.seat("a")], [self.pad("a", 2), self.pad("b", 1)]
        )
        self.assertEqual([p[1] for p in result], [1, 2])

    def test_missing_and_ai_neutral(self):
        self.assertEqual(
            routed([self.seat("a"), self.seat("b", "ai")], [self.pad("b")]),
            [(False, 0, [0] * 6)] * 2,
        )

    def test_duplicate_seat_cannot_borrow_controller(self):
        result = routed([self.seat("a"), self.seat("a")], [self.pad("a")])
        self.assertTrue(result[0][0])
        self.assertFalse(result[1][0])

    def test_back_consumed_and_start_preserved(self):
        self.assertEqual(
            routed([self.seat("a")], [self.pad("a", (1 << 6) | (1 << 7))])[0][1], 1 << 7
        )

    def test_invalid_frame_is_neutral(self):
        bad = self.pad("a")
        bad["axes"] = [65535] * 6
        self.assertEqual(routed([self.seat("a")], [bad]), [(False, 0, [0] * 6)])


if __name__ == "__main__":
    unittest.main()
