import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from views import ViewGroup

class ViewLaunchTests(unittest.TestCase):
    def test_physical_pixel_layout_and_compact_sparse_seats(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SDL_WINDOWS_DPI_SCALING":"1"}), patch("views.subprocess.Popen") as spawn:
            spawn.side_effect = [Mock(pid=101), Mock(pid=102)]
            group = ViewGroup(Path(tmp))
            group._launch([{"index":1},{"index":3}], {1:"first",3:"second"}, {"port":1234,"password":"fixture"})
            for index, call in enumerate(spawn.call_args_list):
                env = call.kwargs["env"]
                self.assertEqual(env["SDL_WINDOWS_DPI_SCALING"], "0")
                self.assertEqual(env["SDL_WINDOWS_DPI_AWARENESS"], "permonitorv2")
                self.assertEqual(env["GAMENIGHT_COUCH_SEAT"], str(index))
                self.assertEqual(env["GAMENIGHT_COUCH_PLAYERS"], "2")
                self.assertTrue(env["GAMENIGHT_CONTROLLER_FRAME"].endswith(f"view-{[1,3][index]}.frame"))

if __name__ == "__main__":
    unittest.main()
