"""Own the isolated world process and stop it through its save-aware bridge."""

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from prototype import command
from runtime import engine_path, connection


def preserve_world(root, name):
    root = root.resolve()
    source, target = (root / "world").resolve(), (root / name).resolve()
    if (
        not source.is_relative_to(root)
        or not target.is_relative_to(root)
        or source == root
        or target == root
    ):
        raise RuntimeError(
            "World recovery path escaped the isolated prototype directory"
        )
    source.rename(target)


class Server:
    def __init__(self, root):
        self.root = root
        self.process = None
        marker = root / "managed/mod-install.json"
        if marker.exists():
            checkpoint = Path(
                json.loads(marker.read_text(encoding="utf8"))["checkpoint"]
            ).resolve()
            if (
                not checkpoint.is_relative_to((root / "checkpoints").resolve())
                or not checkpoint.is_dir()
            ):
                raise RuntimeError(
                    "Invalid recovery checkpoint; preserve world for inspection"
                )
            interrupted = root / ("interrupted-mod-" + str(time.time_ns()))
            preserve_world(root, interrupted.name)
            shutil.copytree(checkpoint, root / "world")
            marker.unlink()

    def start(self):
        if self.process is not None:
            self.check()
            return
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            try:
                probe.bind(("127.0.0.1", connection(self.root)["port"]))
            except OSError:
                raise RuntimeError(
                    "World port is already in use; close the other session first"
                )
        root = self.root
        engine = engine_path(root)
        # Mineclonia's join notification races a client disconnect. A missing
        # peer must not crash the world. Keep this tiny upstream guard reproducible.
        warning = engine / "games/mineclonia/mods/CORE/mcl_init/outdated_warning.lua"
        source = warning.read_text(encoding="utf8")
        source = source.replace(
            "local current_protocol = core.get_player_information(pn).protocol_version",
            "local info = core.get_player_information(pn)\n\tif not info then return end\n\tlocal current_protocol = info.protocol_version",
        )
        if source != warning.read_text(encoding="utf8"):
            if os.environ.get("GAMENIGHT_MINECLONIA_ENGINE"):
                raise RuntimeError(
                    "Installed game lacks the pinned join-race patch; reinstall it"
                )
            warning.write_text(source, encoding="utf8")
        shutil.copytree(
            Path(__file__).parent / "mods/gamenight_bridge",
            root / "world/worldmods/gamenight_bridge",
            dirs_exist_ok=True,
        )
        folder = root / "managed"
        folder.mkdir(exist_ok=True)
        frame = folder / "server.frame"
        frame.write_text(f"{time.monotonic_ns()} 1 0 0 0 0 0 0 0 0", encoding="utf8")
        env = dict(os.environ, GAMENIGHT_CONTROLLER_FRAME=str(frame))
        env.pop("GAMENIGHT_CONTROLLER_PATH", None)
        user = folder / "server-user"
        user.mkdir(exist_ok=True)
        env["LUANTI_USER_PATH"] = str(user)
        started = time.time()
        with (folder / "server-output.log").open("w") as log:
            self.process = subprocess.Popen(
                [
                    str(engine / "bin/luanti.exe"),
                    "--server",
                    "--world",
                    str(root / "world"),
                    "--config",
                    str(root / "server.conf"),
                    "--logfile",
                    str(folder / "server.log"),
                ],
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
            )
        (folder / "server.pid").write_text(str(self.process.pid), encoding="utf8")
        # A cold Windows world can spend over 90 seconds loading Mineclonia mods.
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    "Mineclonia server failed; inspect managed/server-output.log"
                )
            status = root / "world/gamenight/status.json"
            frame.write_text(
                f"{time.monotonic_ns()} 1 0 0 0 0 0 0 0 0", encoding="utf8"
            )
            if status.exists() and status.stat().st_mtime >= started:
                try:
                    state = json.loads(status.read_text(encoding="utf8"))
                except (OSError, json.JSONDecodeError):
                    state = {}
                if state.get("spawn_error"):
                    self.stop()
                    raise RuntimeError(state["spawn_error"])
                if state.get("spawn_ready", False):
                    frame.write_text(
                        f"{time.monotonic_ns()} 0 0 0 0 0 0 0 0 0", encoding="utf8"
                    )
                    return
            time.sleep(0.1)
        self.stop()
        raise TimeoutError("World did not become ready")

    def check(self):
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("World server stopped; the game is no longer ready")
        status = self.root / "world/gamenight/status.json"
        if not status.exists() or time.time() - status.stat().st_mtime > 10:
            raise RuntimeError("World server heartbeat stopped")

    def stop(self):
        process = self.process
        if process is None:
            return
        try:
            if process.poll() is None:
                try:
                    command(self.root, "shutdown")
                    process.wait(timeout=20)
                except (OSError, RuntimeError, TimeoutError, subprocess.TimeoutExpired):
                    # Graceful save is always attempted first. A wedged process
                    # must not remain alive holding the world or private port.
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
        finally:
            self.process = None
