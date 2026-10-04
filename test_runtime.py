import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from runtime import prepare_data, connection, engine_path


class InstalledRuntime(unittest.TestCase):
    def test_new_world_has_dry_spawn_and_private_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            info = prepare_data(root)
            self.assertEqual(connection(root), info)
            self.assertGreater(info["port"], 0)
            self.assertGreater(len(info["password"]), 20)
            config = (root / "server.conf").read_text()
            self.assertIn("gamenight_safe_spawn = true", config)
            self.assertIn("max_users = 4", config)
            self.assertIn("bind_address = 127.0.0.1", config)
            self.assertNotIn("gamenight-couch-prototype", config)

    def test_upgrade_preserves_world_and_seed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prepare_data(root)
            password = connection(root)["password"]
            seed = (root / "world-seed.txt").read_text()
            (root / "world/world.mt").write_text("existing world configuration")
            (root / "world/map.sqlite").write_bytes(b"saved map")
            prepare_data(root)
            self.assertEqual(connection(root)["password"], password)
            self.assertEqual((root / "world-seed.txt").read_text(), seed)
            self.assertEqual(
                (root / "world/world.mt").read_text(), "existing world configuration"
            )
            self.assertEqual((root / "world/map.sqlite").read_bytes(), b"saved map")

    def test_engine_location_is_independent_of_save(self):
        with patch.dict(
            os.environ, {"GAMENIGHT_MINECLONIA_ENGINE": str(Path("engine").resolve())}
        ):
            self.assertEqual(engine_path(Path("save")), Path("engine").resolve())
