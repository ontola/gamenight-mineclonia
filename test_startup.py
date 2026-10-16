import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from managed import Adapter


class StartupTests(unittest.TestCase):
    def make_adapter(self, root):
        with patch("managed.Server") as server:
            server.return_value.start_steps.return_value = iter(
                [
                    "Starting world and loading game assets",
                    "Finding safe starting ground",
                ]
            )
            adapter = Adapter(root, Mock())
        adapter.views = Mock(children=[], frames=[])
        adapter.mod.tick = Mock()
        return adapter

    def prepare(self, adapter, session="test"):
        adapter.receive({"type": "prepare", "session": session, "seats": []})

    def test_prepare_reports_loading_before_world_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self.make_adapter(Path(tmp))
            self.prepare(adapter)
            adapter.views.launch.assert_not_called()
            adapter.send.assert_any_call(
                {
                    "type": "progress",
                    "session": "test",
                    "percent": 0,
                    "label": "Starting world and loading game assets",
                }
            )
            adapter.tick()
            adapter.tick()
            adapter.views.launch.assert_not_called()
            adapter.send.assert_any_call(
                {
                    "type": "progress",
                    "session": "test",
                    "percent": 0,
                    "label": "Finding safe starting ground",
                }
            )
            with patch.object(adapter, "world_ready", return_value=False):
                adapter.tick()
            adapter.views.launch.assert_called_once()
            self.assertLess(time.monotonic() - adapter.started, 1)
            adapter.settings.close()

    def test_dispose_during_loading_never_launches_cancelled_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self.make_adapter(Path(tmp))
            self.prepare(adapter)
            adapter.receive({"type": "dispose", "session": "test"})
            for _ in range(3):
                adapter.tick()
            adapter.views.launch.assert_not_called()
            self.assertIsNone(adapter.session)
            adapter.settings.close()

    def test_reprepare_uses_latest_session_once_world_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self.make_adapter(Path(tmp))
            self.prepare(adapter, "old")
            self.prepare(adapter, "new")
            with patch.object(adapter, "world_ready", return_value=False):
                for _ in range(3):
                    adapter.tick()
            adapter.views.launch.assert_called_once()
            self.assertEqual(adapter.session, "new")
            adapter.settings.close()


if __name__ == "__main__":
    unittest.main()
