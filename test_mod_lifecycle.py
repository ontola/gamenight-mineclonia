import json
from pathlib import Path
import tempfile
from concurrent.futures import Future
import unittest
from unittest.mock import Mock, patch
from managed import Adapter
from mod_session import ModSession
from server import Server


class ModRecovery(unittest.TestCase):
    def adapter(self, root):
        a = Adapter.__new__(Adapter)
        a.mod = ModSession(a)
        self.addCleanup(a.mod.close)
        a.settings = Mock(future=None)
        a.root = root
        a.directory = root / "managed"
        a.directory.mkdir()
        a.mod.request = {
            "id": "e8d5088a-42f7-4278-b322-1eab544b6387",
            "instance": "session",
            "expected_revision": 1,
            "expires": 9999999999,
            "seat": {"index": 0, "player": "player", "revision": 1},
            "values": {"bounce": 1.5},
        }
        a.session = "session"
        a.seats = []
        a.mod.restart = None
        a.mod.future = Future()
        return a

    def test_failed_validation_does_not_touch_live_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            world = root / "world"
            world.mkdir()
            (world / "save").write_text("keep this")
            a = self.adapter(root)
            a.mod.future.set_exception(RuntimeError("failed engine test"))
            with patch.object(a, "dispose") as dispose:
                a.mod.tick()
                dispose.assert_not_called()
            self.assertEqual((world / "save").read_text(), "keep this")
            result = json.loads((a.directory / "mod-result.json").read_text())
            self.assertFalse(result["ok"])
            self.assertIn("failed engine test", result["message"])

    def test_generated_failure_is_available_for_a_repair_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.adapter(Path(tmp))
            a.mod.request["values"] = {"title": "Broken", "code": "invalid Lua"}
            a.mod.future.set_exception(RuntimeError("syntax error"))
            a.mod.tick()
            import modding

            failed = modding.sdk_context(a.root)["failed"]
            self.assertEqual(failed["program"]["code"], "invalid Lua")
            self.assertIn("syntax error", failed["error"])

    def test_generated_join_error_restores_checkpoint_before_success_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = self.adapter(root)
            (root / "world/gamenight").mkdir(parents=True)
            (root / "world/save").write_text("bad candidate")
            (root / "world/gamenight/status.json").write_text(
                json.dumps({"generated_mod": {"error": "join failed"}})
            )
            checkpoint = root / "checkpoints/test"
            checkpoint.mkdir(parents=True)
            (checkpoint / "save").write_text("saved inventory")
            marker = a.directory / "mod-install.json"
            marker.write_text("{}")
            a.server = Mock()
            a.dispose = Mock()
            a.receive = Mock()
            a.mod.restart = True
            a.mod.recovery = ({"type": "prepare"}, True, checkpoint, marker)
            a.mod.tick()
            self.assertEqual((root / "world/save").read_text(), "saved inventory")
            self.assertFalse(marker.exists())
            self.assertTrue(a.resume_when_ready)
            self.assertFalse(
                json.loads((a.directory / "mod-result.json").read_text())["ok"]
            )
            a.receive.assert_called_once()

    def test_departed_player_cancels_install_even_after_test_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.adapter(Path(tmp))
            a.mod.future.set_result("passed")
            with patch.object(a, "dispose") as dispose:
                a.mod.tick()
                dispose.assert_not_called()
            result = json.loads((a.directory / "mod-result.json").read_text())
            self.assertFalse(result["ok"])
            self.assertIn("Player left", result["message"])

    def test_checkpoint_restore_io_failure_is_not_hidden_as_a_stale_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = self.adapter(root)
            (root / "world/gamenight").mkdir(parents=True)
            (root / "world/gamenight/status.json").write_text(
                json.dumps({"generated_mod": {"error": "join failed"}})
            )
            a.mod.restart = True
            with patch.object(
                a.mod, "recover_restart", side_effect=OSError("disk full")
            ):
                with self.assertRaisesRegex(OSError, "disk full"):
                    a.mod.tick()

    def test_interrupted_install_restores_checkpoint_and_retains_failed_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "managed").mkdir()
            (root / "world").mkdir()
            (root / "world/save").write_text("partial install")
            checkpoint = root / "checkpoints/one"
            checkpoint.mkdir(parents=True)
            (checkpoint / "save").write_text("saved before mod")
            (root / "managed/mod-install.json").write_text(
                json.dumps({"checkpoint": str(checkpoint)})
            )
            Server(root)
            self.assertEqual((root / "world/save").read_text(), "saved before mod")
            self.assertEqual(len(list(root.glob("interrupted-mod-*"))), 1)
            self.assertFalse((root / "managed/mod-install.json").exists())

    def test_recovery_refuses_external_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "managed").mkdir()
            (root / "managed/mod-install.json").write_text(
                json.dumps({"checkpoint": str(root.parent)})
            )
            with self.assertRaisesRegex(RuntimeError, "Invalid recovery"):
                Server(root)

    def test_checkpoint_failure_restarts_unchanged_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "world/gamenight").mkdir(parents=True)
            (root / "world/save").write_text("original")
            (root / "world/gamenight/status.json").write_text(
                json.dumps({"revision": 1})
            )
            a = self.adapter(root)
            a.mod.future.set_result("passed")
            a.prepare = {"type": "prepare", "session": "session", "seats": []}
            a.active = True
            a.server = Mock()
            a.receive = Mock()

            def dispose():
                a.session = None

            with (
                patch.object(a, "dispose", side_effect=dispose),
                patch("mod_session.Host.seats", return_value=[a.mod.request["seat"]]),
                patch(
                    "mod_session.modding.stage", return_value=(root / "stage", "hash")
                ),
                patch("mod_session.shutil.copytree", side_effect=OSError("disk full")),
            ):
                a.mod.tick()
            a.server.stop.assert_called_once()
            a.server.start.assert_called_once()
            a.receive.assert_called_once()
            self.assertTrue(a.resume_when_ready)
            self.assertEqual((root / "world/save").read_text(), "original")
            result = json.loads((root / "managed/mod-result.json").read_text())
            self.assertFalse(result["ok"])
            self.assertIn("mod not installed", result["message"])
            self.assertFalse((root / "managed/mod-install.json").exists())


if __name__ == "__main__":
    unittest.main()
