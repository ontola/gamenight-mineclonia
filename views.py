"""Own the client processes, configuration and readiness files for one session."""

import os
import re
import subprocess
import time
from input_frames import publish
from runtime import engine_path, connection


class ViewGroup:
    def __init__(self, root):
        self.root = root
        self.directory = root / "managed"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.children = []
        self.frames = []

    def launch(self, seats, accounts):
        info = connection(self.root)
        try:
            self._launch(seats, accounts, info)
        except BaseException:
            self.close()
            raise

    def _launch(self, seats, accounts, info):
        for view, seat in enumerate(seats):
            index = seat["index"]
            frame = self.directory / f"view-{index}.frame"
            frame.with_suffix(".frame.ready").unlink(missing_ok=True)
            publish(frame, False)
            self.frames.append(frame)
            conf = self.directory / f"view-{index}.conf"
            if not conf.exists():
                conf.write_text(
                    "fullscreen = false\nwindow_maximized = false\npause_on_lost_focus = false\nfps_max = 60\nfps_max_unfocused = 30\nviewing_range = 60\nkeymap_pause = GAMEPAD_BUTTON_6\nkeymap_minimap = \nkeymap_drop = \nkeymap_freemove = \nkeymap_screenshot = \ndebug_log_level = info\nsound_volume = "
                    + ("0.5" if view == 0 else "0")
                    + "\n",
                    encoding="utf8",
                )
            config = conf.read_text(encoding="utf8")
            config = re.sub(
                r"(?m)^sound_volume\s*=.*$",
                "sound_volume = " + ("0.5" if view == 0 else "0"),
                config,
            )
            conf.write_text(config, encoding="utf8")
            env = dict(
                os.environ,
                GAMENIGHT_CONTROLLER_FRAME=str(frame),
                GAMENIGHT_COUCH_SEAT=str(view),
                GAMENIGHT_COUCH_PLAYERS=str(len(seats)),
            )
            env["GAMENIGHT_COUCH_GROUP"] = str(self.directory / "view-pids.txt")
            env.pop("GAMENIGHT_CONTROLLER_PATH", None)
            if os.environ.get("GAMENIGHT_BENCHMARK") == "1":
                env["GAMENIGHT_PERFORMANCE_LOG"] = str(
                    self.directory / f"performance-{index}.csv"
                )
            else:
                env.pop("GAMENIGHT_PERFORMANCE_LOG", None)
            userdir = self.directory / f"client-{index}"
            userdir.mkdir(exist_ok=True)
            env["LUANTI_USER_PATH"] = str(userdir)
            args = [
                str(engine_path(self.root) / "bin/luanti.exe"),
                "--go",
                "--address",
                "127.0.0.1",
                "--port",
                str(info["port"]),
                "--name",
                accounts[index],
                "--password",
                info["password"],
                "--config",
                str(conf),
                "--logfile",
                str(self.directory / f"view-{index}.log"),
            ]
            self.children.append(
                subprocess.Popen(
                    args,
                    cwd=self.root,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
            (self.directory / "view-pids.txt").write_text(
                " ".join(str(c.pid) for c in self.children), encoding="utf8"
            )

    def close(self):
        errors = []
        for child in self.children:
            try:
                if child.poll() is None:
                    child.terminate()
            except OSError as error:
                errors.append(error)
        # One deadline for the whole group, not ten seconds per client.
        deadline = time.monotonic() + 10
        for child in self.children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                try:
                    child.kill()
                    child.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired) as error:
                    errors.append(error)
            except OSError as error:
                errors.append(error)
        self.children.clear()
        self.frames.clear()
        (self.directory / "view-pids.txt").write_text("", encoding="ascii")
        if errors:
            raise RuntimeError("Could not terminate a player view") from errors[0]
