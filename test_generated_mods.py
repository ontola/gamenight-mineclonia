import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import modding

RALLY = """gn.tool('rally',{description='Rally Wand',color='#22aaff'},function(p)
local affected=0
for _,other in ipairs(gn.near(gn.pos(p),4)) do
 if other~=p then gn.push(other,{x=0,y=12,z=0});affected=affected+1 end
end
gn.set('boosts',gn.get('boosts',0)+affected)
end)
gn.on_join(function(p)gn.give_once(p,'rally',1)end)
"""


class GeneratedMods(unittest.TestCase):
    def test_source_is_staged_unchanged_with_trusted_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, digest = modding.stage(Path(tmp), {"title": "Rally", "code": RALLY})
            self.assertEqual((folder / "program.lua").read_text(), RALLY)
            self.assertNotEqual((folder / "init.lua").read_text(), RALLY)
            self.assertEqual(
                json.loads((folder / "recipe.json").read_text())["sha256"], digest
            )
            self.assertEqual(
                modding.stage(Path(tmp), {"title": "Rally", "code": RALLY})[1], digest
            )

    def test_rejects_files_bytecode_oversize_and_bad_types(self):
        for spec in (
            {"title": "x", "code": "x" * 12001},
            {"title": "x", "code": "\x1bLua"},
            {"title": "x", "code": "\x00"},
            {"title": "x", "code": 3},
            {"title": "", "code": "ok"},
            {"title": "x", "code": "ok", "path": "../init.lua"},
        ):
            with self.subTest(spec=str(spec)[:80]), self.assertRaises(ValueError):
                modding.validate_program(spec)

    @unittest.skipUnless(
        shutil.which("luajit"), "LuaJIT required for SDK execution tests"
    )
    def test_callbacks_and_execution_boundaries(self):
        cases = [
            (RALLY, "ok"),
            ("while true do end", "reject"),
            ('local x=("a"):rep(1000000000)', "reject"),
            ('io.open("secret")', "reject"),
            ('return require("ffi")', "reject"),
            (
                'gn.node("x",{description="X",color="#ffffff"});gn.on_tick(function()while true do end end)',
                "runtime_reject",
            ),
            (
                'gn.node("x",{description="X",color="#ffffff"});gn.check(function()assert(false,"bad logic")end)',
                "reject",
            ),
        ]
        for code, mode in cases:
            with (
                self.subTest(mode=mode, code=code),
                tempfile.TemporaryDirectory() as tmp,
            ):
                folder, _ = modding.stage(Path(tmp), {"title": "Test", "code": code})
                done = subprocess.run(
                    [
                        "luajit",
                        str(
                            Path(__file__)
                            .with_suffix(".lua")
                            .with_name("test_generated_sdk.lua")
                        ),
                        str(folder),
                        mode,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
