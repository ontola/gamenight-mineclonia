"""Local experimental Mineclonia adapter for the real GameNight lobby.

The resident lobby owns Back and hardware input. We route host tokens to one to four
engine views; native SDL controller events are disabled in managed clients.
"""

import argparse
import json
import os
from pathlib import Path
import select
import socket
import time
import profiles
import identities
from input_frames import couch_order, local_seats, routed, publish
from views import ViewGroup
from session_state import SessionState
from mod_session import ModSession
from settings import Settings
from couch import singleton
from server import Server
from runtime import prepare_data
from prototype import command, read_json


# Plain-text requests the world understands, for the GameNight app and the
# session assistant. Item names are Mineclonia's English names.
COMMANDS = {
    "type": "declare_commands",
    "description": (
        "Give items to the player who asks, to everyone, or to a named player. "
        "Write one request in Dutch or English with the count and Mineclonia's "
        "English item name. Several items can be joined with commas and 'en'."
    ),
    "examples": [
        "geef me 10 End Crystal",
        "geef me 10 Bread, 3 Golden Apple en 1 Bow",
        "geef iedereen 5 Torch",
        "geef Anna 2 stacks Oak Log",
        "give me 1 Diamond Pickaxe",
    ],
}


class Adapter:
    def __init__(self, root, send):
        self.root, self.send = root, send
        self.server = Server(root)
        self.settings = Settings(root)
        self.directory = root / "managed"
        self.directory.mkdir(exist_ok=True)
        self.server_frame = self.directory / "server.frame"
        self.views = ViewGroup(root)
        self.state = SessionState.IDLE
        self.resume_when_ready = None
        self.seats = []
        self.session = None
        self.controllers = []
        self.received = 0
        self.started = 0
        self.prepare = None
        self.mod = ModSession(self)
        # Keep receiving host messages while the world boots. A cold startup
        # must remain visible in the lobby and cancellable through dispose.
        self._startup = self.server.start_steps()
        self._startup_stage = "Starting world and loading game assets"
        self._progress_at = 0.0

    @property
    def children(self):
        return self.views.children

    @property
    def frames(self):
        return self.views.frames

    @property
    def active(self):
        return self.state == SessionState.PLAYING

    @active.setter
    def active(self, value):
        self.state = SessionState.PLAYING if value else SessionState.PAUSED

    @property
    def ready(self):
        return self.state in (
            SessionState.READY,
            SessionState.PLAYING,
            SessionState.PAUSED,
        )

    def close(self):
        startup = getattr(self, "_startup", None)
        if startup is not None:
            startup.close()
            self._startup = None
        try:
            try:
                self.settings.close()
            finally:
                self.mod.close()
        finally:
            try:
                self.dispose()
            finally:
                self.server.stop()
                self.state = SessionState.CLOSED

    def dispose(self):
        self.state = SessionState.IDLE
        self.resume_when_ready = None
        try:
            self.flush()
            self.settings.settle()
            if (
                self.children
                and self.server.process
                and self.server.process.poll() is None
            ):
                command(self.root, "disconnect_views")
        finally:
            try:
                self.views.close()
            finally:
                self.session = None

    def receive(self, msg):
        kind = msg.get("type")
        if kind == "welcome":
            self.send({"type": "declare_settings", "settings": self.settings.specs()})
            self.send(COMMANDS)
        elif kind == "game_command":
            self.send(self.game_command(msg))
        elif kind == "setting_changed":
            self.settings.change(msg.get("key"), msg.get("value"))
        elif kind == "controller_frame":
            self.controllers = msg["controllers"]
            self.received = time.monotonic()
        elif kind == "prepare":
            if self.mod.request and self.mod.request.get("instance") != msg["session"]:
                self.mod.result(False, "Game instance changed during mod validation")
            # Views open left to right in couch order.
            seats = couch_order(local_seats(msg["seats"]), msg.get("players", []))
            if not seats:
                seats = [{"index": 0, "occupant": {"kind": "empty"}}]
            accounts = identities.accounts(self.root, seats, msg.get("players", []))
            self.dispose()
            self.prepare = dict(msg)
            self.players = msg.get("players", [])
            self.session = msg["session"]
            self.seats = seats
            self.accounts = accounts
            self.state = SessionState.PREPARING
            profiles.publish(self.root, self.seats, self.players, self.accounts)
            self.started = time.monotonic()
            self.send(
                {
                    "type": "participation",
                    "session": self.session,
                    "instant_join": False,
                }
            )
            if getattr(self, "_startup", None) is None:
                self._launch_views()
            else:
                self._report_world_loading()
        elif kind == "party_updated" and msg.get("session") == self.session:
            updates = {seat["index"]: seat for seat in local_seats(msg["seats"])}
            seats = [
                updates.get(
                    seat["index"],
                    {"index": seat["index"], "occupant": {"kind": "empty"}},
                )
                for seat in self.seats
            ]
            # Never let a replacement profile control another person's account.
            # Empty seats stay neutral; their view is retained until reprepare.
            players = msg.get("players", self.players)
            changed = any(
                identities.identity(seat, players) is not None
                and identities.identity(seat, players)
                != identities.identity(old, self.players)
                for seat, old in zip(seats, self.seats)
            )
            if changed:
                active = self.active
                self.receive(dict(self.prepare, seats=seats, players=players))
                self.resume_when_ready = active
                return
            self.seats = seats
            self.players = players
            self.prepare.update(seats=seats, players=players)
            profiles.publish(self.root, self.seats, players, self.accounts)
            self._arrange()
        elif kind == "players_updated" and msg.get("session") == self.session:
            # Same people in the same seats with a new name, face or profile
            # (picked up in the lobby): the world keeps running. A new profile
            # moves that seat to the profile's own account, as a roster
            # update would.
            updates = {
                p.get("id"): p for p in msg.get("players", []) if isinstance(p, dict)
            }
            players = [
                updates.pop(p.get("id"), p) if isinstance(p, dict) else p
                for p in self.players
            ] + list(updates.values())
            self.receive(
                {
                    "type": "party_updated",
                    "session": self.session,
                    "seats": self.seats,
                    "players": players,
                }
            )
        elif (
            kind in ("start", "resume", "pause", "dispose")
            and msg.get("session") == self.session
        ):
            if kind == "dispose":
                self.dispose()
            else:
                active = kind in ("start", "resume")
                if self.state == SessionState.PREPARING:
                    self.resume_when_ready = active
                else:
                    self.active = active
                if self.mod.restart is not None:
                    self.mod.restart = active
                self.flush()
                print(kind, self.session, flush=True)
        elif kind == "error":
            # Startup and roster changes can supersede a preparation while our
            # ready/participation notification is in flight. The host's ordered
            # dispose/prepare messages remain authoritative; a stale notice is
            # not a reason to kill the world or its current views.
            if msg["message"] in (
                "stale participation session",
                "ready for unknown or non-preparing session",
            ) or (
                # Hosts older than plain-text requests refuse the declaration;
                # the world plays on without them.
                msg["message"].startswith("bad message")
                and (
                    "declare_commands" in msg["message"]
                    or "command_result" in msg["message"]
                )
            ):
                print("Superseded lifecycle notification:", msg["message"], flush=True)
                return
            raise RuntimeError(msg["message"])

    def _arrange(self):
        """Players moved on the couch (lobby Start menu): the views trade
        places on screen, without reconnecting anyone."""
        order = [seat["index"] for seat in couch_order(self.seats, self.players)]
        self.views.arrange([order.index(seat["index"]) for seat in self.seats])

    def _report_world_loading(self):
        self.send(
            {
                "type": "progress",
                "session": self.session,
                "percent": 0,
                "label": self._startup_stage,
            }
        )
        self._progress_at = time.monotonic()

    def _launch_views(self):
        self.started = time.monotonic()
        self.send(
            {
                "type": "progress",
                "session": self.session,
                "percent": 50,
                "label": f"World ready. Loading {len(self.seats)} player view(s)",
            }
        )
        # Someone may have moved on the couch while the world loaded.
        self.seats = couch_order(self.seats, self.players)
        self.views.launch(self.seats, self.accounts)

    def flush(self):
        if getattr(self, "_startup", None) is None:
            publish(self.server_frame, self.active)
        pads = routed(
            self.seats,
            self.controllers if time.monotonic() - self.received <= 0.25 else [],
        )
        for i, path in enumerate(self.frames):
            connected, buttons, axes = pads[i] if i < len(pads) else (False, 0, [0] * 6)
            publish(path, self.active, connected, buttons, axes)

    def world_ready(self):
        state = read_json(self.root / "world/gamenight/status.json")
        players = state.get("players") or []
        return {player["name"] for player in players} == set(
            self.accounts.values()
        ) and all(
            player.get("profile", {}).get("hud")
            and player.get("profile", {}).get("skin_applied")
            for player in players
        )

    def game_command(self, msg):
        """Run a plain-text request ("geef me 10 End Crystal") for one seated
        player through the world's chat assistant, and answer the host."""
        answer = {"type": "command_result", "id": msg.get("id", ""), "ok": False}
        account = next(
            (
                self.accounts.get(seat["index"])
                for seat in self.seats
                if seat.get("occupant", {}).get("player_id") == msg.get("player_id")
            ),
            None,
        )
        if not self.session or not self.ready or account is None:
            return {**answer, "message": "Join the running Mineclonia world first."}
        try:
            response = command(
                self.root,
                "assistant",
                {"player": account, "text": str(msg.get("text", ""))[:500]},
            )
        except (RuntimeError, TimeoutError, OSError):
            return {**answer, "message": "The world is busy. Try again in a moment."}
        return {
            **answer,
            "ok": bool(response.get("ok")),
            "message": response.get("message") or response.get("error") or "Done.",
        }

    def tick(self):
        startup = getattr(self, "_startup", None)
        if startup is not None:
            try:
                stage = next(startup)
            except StopIteration:
                self._startup = None
                if self.session:
                    self._launch_views()
            else:
                changed = stage != self._startup_stage
                self._startup_stage = stage
                if self.session and (
                    changed or time.monotonic() - self._progress_at > 5
                ):
                    self._report_world_loading()
                return
        self.server.check()
        self.views.retry()
        self.settings.tick(blocked=self.mod.request is not None)
        self.mod.tick()
        if any(c.poll() is not None for c in self.children):
            raise RuntimeError("A Mineclonia view closed; ending this session")
        if self.session and not self.ready:
            if (
                all(Path(str(f) + ".ready").exists() for f in self.frames)
                and 1 <= len(self.frames) <= 4
                and self.world_ready()
            ):
                self.state = SessionState.READY
                if self.resume_when_ready is not None:
                    self.active = self.resume_when_ready
                    self.resume_when_ready = None
                if self.mod.restart is not None:
                    self.active = self.mod.restart
                    self.mod.result(
                        True,
                        "Previous mod restored; all player views reconnected."
                        if self.mod.request.get("undo")
                        else "Bounce pad installed and all player views reconnected. Players receive bounce pads in their inventory when space is available. Set bounce to zero to disable the effect.",
                    )
                    (self.directory / "mod-install.json").unlink(missing_ok=True)
                else:
                    self.send({"type": "ready", "session": self.session})
                print("All player views rendered; ready", flush=True)
            elif time.monotonic() - self.started > 180:
                raise RuntimeError("Timed out loading Mineclonia views")
        self.flush()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--root", type=Path, default=Path("E:/gamenight-host/prototypes/mineclonia")
    )
    p.add_argument("--installed", action="store_true")
    a = p.parse_args()
    a.root = a.root.resolve()
    a.root.mkdir(parents=True, exist_ok=True)
    if not os.environ.get("GAMENIGHT_TOKEN"):
        raise SystemExit("Launch through the GameNight test shelf, not directly.")
    host, port = os.environ["GAMENIGHT_ADDR"].rsplit(":", 1)
    with singleton(a.root), socket.create_connection((host, int(port))) as sock:
        if a.installed:
            prepare_data(a.root)

        def send(msg):
            sock.sendall((json.dumps(msg) + "\n").encode())

        send(
            {
                "type": "hello",
                "role": "game",
                "game": os.environ["GAMENIGHT_GAME_ID"],
                "token": os.environ["GAMENIGHT_TOKEN"],
            }
        )
        adapter = Adapter(a.root, send)
        buffer = b""
        try:
            while True:
                if select.select([sock], [], [], 0.016)[0]:
                    data = sock.recv(65536)
                    if not data:
                        break
                    buffer += data
                    if len(buffer) > 16777216:
                        raise RuntimeError("Oversized host message")
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if line:
                            adapter.receive(json.loads(line))
                adapter.tick()
        finally:
            adapter.close()


if __name__ == "__main__":
    main()
