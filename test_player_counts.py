import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from views import ViewGroup
from session_state import SessionState
from managed import Adapter, local_seats, routed


def seat(i, kind="local"):
    return {
        "index": i,
        "occupant": {"kind": kind, "player_id": f"p{i}"},
        "controller": f"pad{i}",
    }


class PlayerCounts(unittest.TestCase):
    def test_empty_and_ai_do_not_create_views(self):
        self.assertEqual(
            local_seats([seat(0, "empty"), seat(3), seat(1, "ai")]), [seat(3)]
        )
        for bad in ([seat(0), seat(0)], [seat(4)], [seat(True)], [seat("1"), seat(0)]):
            with self.assertRaises(ValueError):
                local_seats(bad)

    def test_prepare_launches_only_occupied_seats_and_packs_views(self):
        for indices in ([0], [3], [0, 1], [1, 3], [0, 1, 2], [0, 1, 2, 3]):
            with self.subTest(indices=indices), tempfile.TemporaryDirectory() as tmp:
                a = Adapter.__new__(Adapter)
                a.root = Path(tmp)
                a.directory = a.root / "managed"
                a.directory.mkdir()
                a.mod = Mock(request=None, restart=None)
                a.views = ViewGroup(a.root)
                a.controllers = []
                a.resume_when_ready = None
                a.dispose = Mock()
                a.send = Mock()
                a.world_ready = Mock(return_value=True)
                seats = [
                    seat(i, "local" if i in indices else "empty") for i in range(4)
                ]
                with patch("views.subprocess.Popen") as launch:
                    launch.return_value.pid = 123
                    a.receive({"type": "prepare", "session": "s", "seats": seats})
                self.assertEqual(launch.call_count, len(indices))
                for view, (index, call) in enumerate(
                    zip(indices, launch.call_args_list)
                ):
                    self.assertEqual(
                        call.kwargs["env"]["GAMENIGHT_COUCH_SEAT"], str(view)
                    )
                    self.assertEqual(
                        call.kwargs["env"]["GAMENIGHT_COUCH_PLAYERS"], str(len(indices))
                    )
                    self.assertIn(f"Couch{index + 1}", call.args[0])
                    self.assertEqual(a.frames[view].name, f"view-{index}.frame")
                a.send.assert_any_call(
                    {"type": "participation", "session": "s", "instant_join": False}
                )
                # A disconnected first seat must not shift the other player's frame.
                a.receive(
                    {
                        "type": "party_updated",
                        "session": "s",
                        "seats": [seat(i) for i in indices[1:]],
                    }
                )
                self.assertEqual([s["index"] for s in a.seats], list(indices))
                pads = [
                    {"controller": f"pad{i}", "buttons": i + 1, "axes": [0] * 6}
                    for i in reversed(indices)
                ]
                routed_pads = routed(a.seats, pads)
                self.assertFalse(routed_pads[0][0])
                self.assertEqual(
                    [p[1] for p in routed_pads[1:]], [i + 1 for i in indices[1:]]
                )

    def test_ready_waits_for_every_view(self):
        for count in range(1, 5):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as tmp:
                a = Adapter.__new__(Adapter)
                a.server = Mock()
                a.settings = Mock()
                a.flush = Mock()
                a.send = Mock()
                a.world_ready = Mock(return_value=True)
                a.mod = Mock(request=None, restart=None)
                a.views = ViewGroup(Path(tmp))
                a.session = "s"
                a.state = SessionState.PREPARING
                a.resume_when_ready = None
                a.started = time.monotonic()
                a.views.frames = [Path(tmp) / f"{i}.frame" for i in range(count)]
                for frame in a.frames[:-1]:
                    Path(str(frame) + ".ready").touch()
                a.tick()
                self.assertFalse(a.ready)
                Path(str(a.frames[-1]) + ".ready").touch()
                a.tick()
                self.assertTrue(a.ready)
                a.send.assert_called_once_with({"type": "ready", "session": "s"})
