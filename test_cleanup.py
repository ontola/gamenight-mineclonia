from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from managed import Adapter
from server import Server
from session_state import SessionState
from views import ViewGroup


class CleanupTests(unittest.TestCase):
    def test_bridge_failure_still_closes_every_view(self):
        with tempfile.TemporaryDirectory() as temp:
            adapter = Adapter.__new__(Adapter)
            adapter.root = Path(temp)
            adapter.views = ViewGroup(adapter.root)
            child = Mock()
            child.poll.return_value = None
            adapter.views.children = [child]
            adapter.session = "session"
            adapter.flush = Mock()
            adapter.settings = Mock()
            adapter.server = Mock()
            adapter.server.process.poll.return_value = None
            with patch(
                "managed.command", side_effect=RuntimeError("bridge unavailable")
            ):
                with self.assertRaises(RuntimeError):
                    adapter.dispose()
            child.terminate.assert_called_once()
            child.wait.assert_called_once()
            self.assertEqual(adapter.state, SessionState.IDLE)
            self.assertIsNone(adapter.session)
            self.assertEqual(adapter.children, [])

    def test_second_view_launch_failure_reaps_first_child(self):
        with tempfile.TemporaryDirectory() as temp:
            group = ViewGroup(Path(temp))
            child = Mock(pid=123)
            child.poll.return_value = None
            with patch(
                "views.subprocess.Popen", side_effect=[child, OSError("launch failed")]
            ):
                with self.assertRaises(OSError):
                    group.launch(
                        [{"index": 0}, {"index": 1}], {0: "Couch1", 1: "Couch2"}
                    )
            child.terminate.assert_called_once()
            self.assertEqual(group.children, [])
            self.assertEqual(group.frames, [])

    def test_unresponsive_server_is_reaped_after_graceful_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            server = Server(Path(temp))
            process = server.process = Mock()
            process.poll.return_value = None
            process.wait.side_effect = [subprocess.TimeoutExpired("server", 5), None]
            with patch("server.command", side_effect=TimeoutError("no heartbeat")):
                server.stop()
            process.terminate.assert_called_once()
            process.kill.assert_called_once()
            self.assertIsNone(server.process)

    def test_start_during_preparation_waits_for_all_renderers(self):
        adapter = Adapter.__new__(Adapter)
        adapter.session = "session"
        adapter.state = SessionState.PREPARING
        adapter.mod = Mock(restart=None)
        adapter.flush = Mock()
        adapter.receive({"type": "start", "session": "session"})
        self.assertFalse(adapter.active)
        self.assertFalse(adapter.ready)
        self.assertTrue(adapter.resume_when_ready)

    def test_cancelled_validation_reaps_its_isolated_server(self):
        from threading import Event
        import modding

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged, _ = modding.stage(root, {"bounce": 1})
            cancelled = Event()
            cancelled.set()
            process = Mock()
            process.poll.return_value = None
            with patch("modding.subprocess.Popen", return_value=process):
                with self.assertRaisesRegex(RuntimeError, "cancelled"):
                    modding.validate(root, staged, cancelled)
            process.terminate.assert_called_once()
            process.wait.assert_called_once()
