"""Contract checks for the experimental host boundary; no synthetic gameplay."""

import time, unittest, tempfile
from pathlib import Path
from unittest.mock import patch, Mock
from relay import execute, snapshot


class Contract(unittest.TestCase):
    def test_pairing_stays_available_without_running_world(self):
        host = Mock()
        host.status.return_value = {}
        host.seats.return_value = [{"index": 0, "player": "guest", "revision": 1}]
        with tempfile.TemporaryDirectory() as folder:
            state = snapshot(Path(folder), "test", host=host, allow_loading=True)
            self.assertEqual(state["seats"], host.seats.return_value)
            self.assertIsNone(state["discovery"]["controls"])
            self.assertEqual(
                snapshot(Path(folder), "test", host=host)["seats"], state["seats"]
            )

    def test_other_game_uses_declared_controls_without_a_mineclonia_world(self):
        host = Mock()
        host.status.return_value = {
            "active_session": {"id": "game-1", "game": "neon-siege"},
            "connected_games": ["neon-siege"],
            "library": [
                {"id": "neon-siege"},
                {"id": "mineclonia-prototype"},
                {"id": "lobby"},
            ],
            "settings": [
                {
                    "game": "neon-siege",
                    "revision": 3,
                    "can_undo": True,
                    "specs": [
                        {"key": "wormholes", "kind": "toggle", "label": "Wormholes"}
                    ],
                    "values": {"wormholes": False},
                }
            ],
        }
        host.seats.return_value = [{"index": 0, "player": "guest", "revision": 1}]
        with tempfile.TemporaryDirectory() as folder:
            state = snapshot(
                Path(folder), "test", host=host, receipt={"id": "done", "ok": True}
            )
            c = state["discovery"]["controls"]
            self.assertEqual(c["game"], "neon-siege")
            self.assertEqual(c["settings"]["wormholes"]["value"], False)
            self.assertEqual(
                {g["id"] for g in state["discovery"]["games"]},
                {"neon-siege", "mineclonia"},
            )
            self.assertEqual(state["discovery"]["acknowledged"], "done")

    def test_local_and_installed_mineclonia_are_one_discovery_game(self):
        import game_controls
        host = Mock()
        host.status.return_value = {
            "library": [{"id": game} for game in (
                "mineclonia-prototype", "godot-lobby", "mineclonia", "ballkickers"
            )]
        }
        host.seats.return_value = []
        games = game_controls.snapshot(host)["discovery"]["games"]
        self.assertEqual([game["id"] for game in games], ["mineclonia", "ballkickers"])

    def test_upcoming_settings_use_the_selected_session(self):
        import game_controls

        host = Mock()
        host.status.return_value = {
            "active_session": {
                "id": "current",
                "game": "neon-siege",
                "phase": "running",
            },
            "warm_session": {"id": "next", "game": "space-racer", "phase": "ready"},
            "connected_games": ["neon-siege", "space-racer"],
            "playlist": {
                "current": 0,
                "entries": [
                    {"game": "neon-siege", "title": "Neon Siege"},
                    {"game": "space-racer", "title": "Space Racer"},
                ],
            },
            "settings": [
                {
                    "game": game,
                    "revision": 0,
                    "specs": [{"key": "items", "kind": "toggle", "label": "Items"}],
                    "values": {"items": True},
                }
                for game in ("neon-siege", "space-racer")
            ],
        }
        seat = {"index": 0, "player": "guest", "revision": 1}
        host.seats.return_value = [seat]
        state = game_controls.snapshot(host)["discovery"]
        self.assertEqual(state["controls"]["instance"], "current")
        self.assertEqual(state["next_controls"]["instance"], "next")
        self.assertEqual(state["playlist"]["entries"][1]["game"], "space-racer")

        def accept(command, receipt=False):
            self.assertEqual(command["session"], "next")
            self.assertEqual(command["game"], "space-racer")
            host.status.return_value["settings"][1]["revision"] += 1
            return {
                "type": "settings_accepted",
                "game": "space-racer",
                "session": "next",
                "revision": 1,
            }

        host.request.side_effect = accept
        selection = {
            "id": "request",
            "game": "space-racer",
            "seat": seat,
            "expires": time.time() + 60,
            "command": {
                "action": "set",
                "instance": "next",
                "expected_revision": 0,
                "values": {"items": False},
            },
        }
        self.assertTrue(game_controls.execute(host, selection)["ok"])
        self.assertEqual(host.status.return_value["settings"][0]["revision"], 0)
        host.status.return_value["warm_session"] = None
        host.request.reset_mock()
        with self.assertRaisesRegex(ValueError, "selected game changed"):
            game_controls.execute(host, selection)
        host.request.assert_not_called()

    def request(self):
        return {
            "id": "request-1",
            "game": "mineclonia",
            "expires": int(time.time()) + 60,
            "seat": {"index": 0, "player": "Couch1", "revision": 1},
            "command": {
                "action": "set",
                "instance": "world-1",
                "expected_revision": 2,
                "values": {"gravity": 0.5},
            },
        }

    def test_launch_passes_the_selected_count_to_the_host(self):
        for count in range(1, 5):
            req = self.request()
            req["command"].update(action="launch", values={"players": count})
            current = {
                "seats": [req["seat"]],
                "discovery": {"controls": {"instance": "world-1", "revision": 2}},
            }
            host = Mock()
            with patch("relay.snapshot", return_value=current):
                result = execute(Path("."), "world-1", req, host=host)
                self.assertTrue(result["ok"])
                self.assertEqual(host.launch.call_args.args, (req["seat"], count))
        for count in (0, 5, True, 2.0):
            req["command"]["values"] = {"players": count}
            with (
                patch("relay.snapshot", return_value=current),
                self.assertRaises(ValueError),
            ):
                execute(Path("."), "world-1", req, host=host)

    def test_reject_before_mailbox(self):
        cases = []
        r = self.request()
        r["command"]["values"] = {"shell": 1}
        cases.append(r)
        r = self.request()
        r["command"]["values"] = {"gravity": True}
        cases.append(r)
        r = self.request()
        r["command"]["values"] = {"gravity": float("nan")}
        cases.append(r)
        r = self.request()
        r["command"]["values"] = {"gravity": 0}
        cases.append(r)
        r = self.request()
        del r["command"]["expected_revision"]
        cases.append(r)
        r = self.request()
        r["command"]["instance"] = "other-world"
        cases.append(r)
        r = self.request()
        r["expires"] = 0
        cases.append(r)
        r = self.request()
        r["seat"]["revision"] = 2
        cases.append(r)
        r = self.request()
        r["command"]["action"] = "shutdown"
        cases.append(r)
        with (
            patch(
                "relay.snapshot",
                return_value={
                    "seats": [self.request()["seat"]],
                    "discovery": {"controls": {"instance": "world-1"}},
                },
            ),
            patch("relay.command") as command,
        ):
            for r in cases:
                with self.subTest(r=r), self.assertRaises(ValueError):
                    execute(Path("."), "world-1", r)
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
