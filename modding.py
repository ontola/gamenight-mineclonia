"""Stage generated Lua behind the public SDK and test it in an isolated engine."""

import hashlib
import json
import math
import os
import shutil
import subprocess
import time
import uuid
import socket
import re
from pathlib import Path

SDK = Path(__file__).parent / "mod_sdk"
SDK_VERSION = "gamenight-lua-v1"


def validate_program(values):
    if not isinstance(values, dict) or set(values) != {"title", "code"}:
        raise ValueError("Generated mods require title and code")
    if (
        not isinstance(values["title"], str)
        or not 1 <= len(values["title"].encode()) <= 80
    ):
        raise ValueError("Mod title must be 1 to 80 UTF-8 bytes")
    code = values["code"]
    if (
        not isinstance(code, str)
        or len(code.encode()) > 12000
        or "\x00" in code
        or "\x1b" in code
    ):
        raise ValueError("Mod code must be Lua text of at most 12000 UTF-8 bytes")
    return code


def sdk_context(root):
    current = None
    manifest = root / "world/gamenight/mod-current.json"
    if manifest.exists():
        values = json.loads(manifest.read_text(encoding="utf8")).get("values", {})
        if "code" in values:
            validate_program(values)
            current = values
    return {
        "version": SDK_VERSION,
        "api": (SDK / "API.txt").read_text(encoding="utf8"),
        "current": current,
        "failed": json.loads(
            (root / "managed/mod-failure.json").read_text(encoding="utf8")
        )
        if (root / "managed/mod-failure.json").exists()
        else None,
    }


from runtime import engine_path


def generate(values):
    if not isinstance(values, dict) or set(values) != {"bounce"}:
        raise ValueError("Supported recipe: bounce pad with a bounce strength")
    strength = values["bounce"]
    if (
        type(strength) not in (int, float)
        or not math.isfinite(strength)
        or not 0 <= strength <= 3
    ):
        raise ValueError(
            "Bounce strength must be between 0 and 3; zero disables the effect"
        )
    # Only this validated number enters a fixed Lua program. No paths, URLs,
    # identifiers, Lua source or free-form strings cross the execution boundary.
    return """local strength = %s
core.register_node("gamenight_custom:bounce_pad", {
    description = "GameNight bounce pad",
    tiles = {"default_steel_block.png^[colorize:#ad6cfa:180"},
    groups = {cracky=1, pickaxey=1}, _mcl_hardness=1, _mcl_blast_resistance=1,
})
local elapsed = 0
local cooldown = {}
core.register_globalstep(function(dt)
    elapsed = elapsed + dt
    if strength <= 0 then return end
    for _, p in ipairs(core.get_connected_players()) do
        local pos = p:get_pos()
        local below = core.get_node({x=pos.x,y=pos.y-0.2,z=pos.z})
        local name = p:get_player_name()
        if below.name == "gamenight_custom:bounce_pad" and elapsed >= (cooldown[name] or 0) then
            p:add_velocity({x=0,y=8*strength,z=0})
            cooldown[name] = elapsed + 0.8
        end
    end
end)
core.register_on_joinplayer(function(p)
    if strength <= 0 then return end
    local meta = p:get_meta()
    if meta:get_int("gamenight_bounce_pad_given") == 0 then
        local remaining = p:get_inventory():add_item("main", "gamenight_custom:bounce_pad 8")
        if remaining:is_empty() then meta:set_int("gamenight_bounce_pad_given",1) end
    end
end)
""" % format(strength, ".9g")


def stage(root, values):
    generated = isinstance(values, dict) and "code" in values
    source = validate_program(values) if generated else generate(values)
    runtime = (SDK / "runtime.lua").read_text(encoding="utf8") if generated else ""
    digest = hashlib.sha256((runtime + "\n" + source).encode()).hexdigest()
    folder = root / "mods-staged" / digest
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "init.lua").write_text(runtime if generated else source, encoding="utf8")
    if generated:
        (folder / "program.lua").write_text(source, encoding="utf8")
    (folder / "mod.conf").write_text(
        "name = gamenight_custom\ndepends = mcl_core\n", encoding="utf8"
    )
    (folder / "recipe.json").write_text(
        json.dumps({"version": 1, "values": values, "sha256": digest}), encoding="utf8"
    )
    return folder, digest


def validate(root, staged, cancelled=None):
    """Real Mineclonia startup in a fresh test world. No live save is mounted."""
    world = root / "mod-tests" / uuid.uuid4().hex
    world.mkdir(parents=True)
    (world / "world.mt").write_text(
        "gameid = mineclonia\nbackend = sqlite3\nplayer_backend = sqlite3\nauth_backend = sqlite3\nmod_storage_backend = sqlite3\nload_mod_gamenight_custom = true\nload_mod_gamenight_validation = true\n",
        encoding="utf8",
    )
    shutil.copytree(staged, world / "worldmods/gamenight_custom")
    harness = world / "worldmods/gamenight_validation"
    harness.mkdir()
    (harness / "mod.conf").write_text(
        "name = gamenight_validation\ndepends = gamenight_custom\n", encoding="utf8"
    )
    # Validation exercises registration/callbacks, not terrain generation. This
    # is Mineclonia's supported per-mod switch, read before levelgen initializes.
    (harness / "mcl_levelgen.conf").write_text(
        "disable_mcl_levelgen = true\n", encoding="utf8"
    )
    (harness / "init.lua").write_text(
        """local validated = false
core.register_globalstep(function()
 if validated then return end
 validated = true
 if gamenight_generated_validate then gamenight_generated_validate()
 else assert(core.registered_nodes["gamenight_custom:bounce_pad"], "Missing generated node") end
 core.safe_file_write(core.get_worldpath() .. "/validated", "ok")
 core.request_shutdown("Validation complete", false, 0)
end)
""",
        encoding="utf8",
    )
    config = world / "test.conf"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    config.write_text(
        f"bind_address = 127.0.0.1\nport = {port}\nserver_announce = false\nmg_name = singlenode\nmcl_singlenode_mapgen = false\nfixed_map_seed = 12345\n",
        encoding="utf8",
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("GAMENIGHT_CONTROLLER_FRAME", "GAMENIGHT_CONTROLLER_PATH")
    }
    env["LUANTI_USER_PATH"] = str(world / "user")
    with (world / "test.log").open("w") as log:
        proc = subprocess.Popen(
            [
                str(engine_path(root) / "bin/luanti.exe"),
                "--server",
                "--world",
                str(world),
                "--config",
                str(config),
            ],
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
        )
        deadline = time.monotonic() + 90
        try:
            while True:
                if cancelled is not None and cancelled.is_set():
                    raise RuntimeError(
                        "Mod validation cancelled because the session closed"
                    )
                if time.monotonic() >= deadline:
                    raise TimeoutError("Generated mod test exceeded 90 seconds")
                try:
                    code = proc.wait(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
    if code or not (world / "validated").exists():
        log_text = (world / "test.log").read_text(encoding="utf8", errors="replace")
        messages = re.findall(r"gamenight-generated:[^\n]+", log_text)
        detail = (
            messages[0][:700]
            if messages
            else "See the isolated validation log for details."
        )
        raise RuntimeError(
            "Generated mod failed its isolated engine test; live world unchanged. "
            + detail
        )
    return world


def request(root, values, expected, request_id, seat, expires, instance, undo=False):
    uuid.UUID(request_id)
    # The owned game adapter performs the stop/checkpoint/install/reconnect.
    if undo:
        if values:
            raise ValueError("Undo does not take new values")
        manifest = json.loads(
            (root / "world/gamenight/mod-current.json").read_text(encoding="utf8")
        )
        values = manifest.get("previous_values")
        if values is None:
            raise ValueError("No mod to undo")
    if isinstance(values, dict) and "code" in values:
        validate_program(values)
    else:
        generate(values)
    folder = root / "managed"
    payload = {
        "id": request_id,
        "values": values,
        "expected_revision": expected,
        "seat": seat,
        "expires": expires,
        "instance": instance,
        "undo": undo,
    }
    temp = folder / "mod-request.tmp"
    temp.write_text(json.dumps(payload), encoding="utf8")
    temp.replace(folder / "mod-request.json")
    deadline = time.monotonic() + 350
    while time.monotonic() < deadline:
        try:
            result = json.loads((folder / "mod-result.json").read_text(encoding="utf8"))
            if result.get("id") == request_id:
                return result
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(0.2)
    raise TimeoutError("Mod restart was not confirmed. Check the host before retrying.")
