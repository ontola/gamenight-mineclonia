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

    def test_old_hosts_refusing_plain_text_requests_do_not_close_world(self):
        adapter = Adapter.__new__(Adapter)
        adapter.receive(
            {
                "type": "error",
                "message": "bad message: unknown variant `declare_commands`, expected one of",
            }
        )

    def test_plain_text_requests_run_for_the_asking_player_only(self):
        from session_state import SessionState

        adapter = Adapter.__new__(Adapter)
        adapter.root, adapter.session, adapter.state = None, "s1", SessionState.PLAYING
        adapter.seats = [{"index": 1, "occupant": {"kind": "local", "player_id": "a"}}]
        adapter.accounts = {1: "GN_0123456789abcdef"}
        reply = {"ok": True, "message": "Alsjeblieft: 10× End Crystal."}
        with mock.patch("managed.command", return_value=reply) as run:
            answer = adapter.game_command(
                {"id": "r1", "player_id": "a", "text": "geef me 10 End Crystal"}
            )
        run.assert_called_once_with(
            None,
            "assistant",
            {"player": "GN_0123456789abcdef", "text": "geef me 10 End Crystal"},
        )
        self.assertEqual(
            answer,
            {
                "type": "command_result",
                "id": "r1",
                "ok": True,
                "message": reply["message"],
            },
        )
        with mock.patch("managed.command") as run:
            answer = adapter.game_command({"id": "r2", "player_id": "b", "text": "x"})
        run.assert_not_called()
        self.assertFalse(answer["ok"])
        with mock.patch("managed.command", side_effect=RuntimeError("busy")):
            answer = adapter.game_command({"id": "r3", "player_id": "a", "text": "x"})
        self.assertFalse(answer["ok"])

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
        adapter.views = mock.Mock()
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

    def test_views_open_in_couch_order_and_trade_places_live(self):
        from views import ViewGroup

        seats = [
            {
                "index": i,
                "controller": f"ordinal:{i}",
                "occupant": {"kind": "local", "player_id": p},
            }
            for i, p in enumerate("abc")
        ]
        players = [
            {"id": "a", "couch": 2},
            {"id": "b", "couch": 0},
            {"id": "c", "couch": 1},
        ]
        adapter = Adapter.__new__(Adapter)
        adapter.session, adapter.root = "s1", None
        adapter.seats, adapter.players = list(seats), players
        adapter.accounts = {0: "Couch1", 1: "Couch2", 2: "Couch3"}
        adapter.views = ViewGroup.__new__(ViewGroup)
        adapter.views.children, adapter.views.slots, adapter.views.wanted = [], [], None
        adapter.send = lambda message: None

        def launch(seats, accounts):
            adapter.views.children = [mock.Mock(pid=100 + s["index"]) for s in seats]
            adapter.views.slots = list(range(len(seats)))

        with mock.patch.object(adapter.views, "launch", side_effect=launch):
            adapter._launch_views()
        # Leftmost on the couch gets the leftmost view.
        self.assertEqual(
            [s["occupant"]["player_id"] for s in adapter.seats], ["b", "c", "a"]
        )

        adapter.prepare = {
            "type": "prepare",
            "session": "s1",
            "seats": adapter.seats,
            "players": players,
        }
        with (
            mock.patch("managed.profiles.publish"),
            mock.patch("views.sys.platform", "win32"),
            mock.patch("views.window_layout.trade", return_value=True) as trade,
        ):
            adapter.receive(
                {
                    "type": "players_updated",
                    "session": "s1",
                    "players": [
                        {"id": "a", "couch": 0},
                        {"id": "b", "couch": 1},
                        {"id": "c", "couch": 2},
                    ],
                }
            )
        self.assertEqual(adapter.session, "s1", "nobody reconnects")
        trade.assert_called_once_with([101, 102, 100], [0, 1, 2], [1, 2, 0])
        self.assertEqual(adapter.views.slots, [1, 2, 0])

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
