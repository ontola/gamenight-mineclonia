import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import game_functions


def lua(value):
    if isinstance(value, dict):
        return (
            "{"
            + ",".join("[" + json.dumps(k) + "]=" + lua(v) for k, v in value.items())
            + "}"
        )
    if isinstance(value, list):
        return "{" + ",".join(lua(v) for v in value) + "}"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return json.dumps(value, ensure_ascii=False)


class GameFunctions(unittest.TestCase):
    def setUp(self):
        self.api = json.loads(
            (Path(__file__).parent / "mods/gamenight_bridge/functions.json").read_text()
        )

    def test_empty_parameters_from_engine_remain_a_callable_object(self):
        self.api["functions"]["players.list"]["parameters"] = None
        fixed = game_functions.contract(self.api)
        game_functions.validate(fixed, {"name": "players.list", "arguments": {}})
        self.assertIsNone(self.api["functions"]["players.list"]["parameters"])

    def test_documented_arguments_and_unknown_functions(self):
        good = {
            "name": "inventory.give",
            "arguments": {"target": "self", "item": "Diamond Sword", "count": 2},
        }
        game_functions.validate(self.api, good)
        cases = [
            dict(good, name="core.eval"),
            dict(good, caller="other"),
            dict(
                good,
                arguments={"target": "self", "item": "Diamond Sword", "count": True},
            ),
            dict(
                good,
                arguments={"target": "self", "item": "Diamond Sword", "count": 1.5},
            ),
            dict(
                good,
                arguments={"target": "self", "item": "Diamond Sword", "count": 300},
            ),
            dict(good, arguments={"target": "self", "count": 2}),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                game_functions.validate(self.api, case)
        self.api["functions"]["game.custom_function"] = {
            "description": "Added by a game",
            "returns": "A value",
            "mutates": False,
            "parameters": {},
        }
        game_functions.validate(
            self.api, {"name": "game.custom_function", "arguments": {}}
        )

    def test_caller_is_injected_from_profile_ownership_and_revision_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "world/gamenight"
            folder.mkdir(parents=True)
            (folder / "identities.json").write_text(
                json.dumps({"profiles": {"profile-1": "Couch2"}})
            )
            selection = {
                "id": "request-1",
                "seat": {"player": "profile-1"},
                "command": {
                    "action": "call",
                    "expected_revision": 3,
                    "values": {
                        "name": "inventory.give",
                        "arguments": {
                            "target": "self",
                            "item": "Diamond Sword",
                            "count": 2,
                        },
                    },
                },
            }
            c = {"game_api": self.api, "revision": 3}
            with patch(
                "game_functions.command",
                return_value={
                    "ok": True,
                    "result": {"summary": "Two swords received.", "delivered": 2},
                },
            ) as command:
                result = game_functions.execute(root, selection, c)
                self.assertEqual(command.call_args.args[2]["caller"], "Couch2")
                self.assertEqual(command.call_args.kwargs["request_id"], "request-1")
                self.assertEqual(result["message"], "Two swords received.")
                self.assertEqual(result["data"]["delivered"], 2)
                c["revision"] = 4
                with self.assertRaises(ValueError):
                    game_functions.execute(root, selection, c)
                self.assertEqual(command.call_count, 1)
            selection["seat"]["player"] = "unmapped"
            with self.assertRaises(ValueError):
                game_functions.caller_account(root, selection["seat"])

    @unittest.skipUnless(shutil.which("luajit"), "LuaJIT required")
    def test_engine_handlers_and_dynamic_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "functions.lua"
            fixture.write_text("return " + lua(self.api), encoding="utf8")
            subprocess.run(
                [
                    "luajit",
                    str(Path(__file__).parent / "test_game_functions.lua"),
                    str(fixture),
                    str(Path(__file__).parent / "mods/gamenight_bridge/functions.lua"),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
