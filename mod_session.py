"""Validate, checkpoint, install and recover a session's bounded game mod."""

from concurrent.futures import ThreadPoolExecutor
import json
import shutil
import time
import uuid
from threading import Event
import modding
from host import Host
from server import preserve_world


class ModSession:
    def __init__(self, adapter):
        self.adapter = adapter
        self.cancelled = Event()
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.request = None
        self.future = None
        self.restart = None

    def close(self):
        self.cancelled.set()
        self.worker.shutdown(wait=True, cancel_futures=True)

    def result(self, ok, message):
        result = {"id": self.request["id"], "ok": ok, "message": message}
        target = self.adapter.directory / "mod-result.json"
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(result), encoding="utf8")
        temp.replace(target)
        self.request = self.future = self.restart = None

    def tick(self):
        if self.adapter.settings.future is not None:
            return
        path = self.adapter.directory / "mod-request.json"
        if path.exists() and self.request is None:
            req = json.loads(path.read_text(encoding="utf8"))
            path.unlink()
            uuid.UUID(req["id"])
            if req.get("instance") != self.adapter.session:
                self.request = req
                self.result(False, "Game instance changed")
                return
            self.request = req
            try:
                state = json.loads(
                    (self.adapter.root / "world/gamenight/status.json").read_text(
                        encoding="utf8"
                    )
                )
                if state["revision"] != req["expected_revision"]:
                    raise ValueError("World changed before mod validation")
                staged, digest = modding.stage(self.adapter.root, req["values"])
                self.future = self.worker.submit(
                    modding.validate, self.adapter.root, staged, self.cancelled
                )
            except (ValueError, OSError, RuntimeError) as e:
                self.result(False, str(e))
        if self.future and self.future.done():
            try:
                self.future.result()
                if (
                    self.request.get("instance") != self.adapter.session
                    or self.request["expires"] <= time.time()
                    or self.request["seat"]
                    not in Host.seats({"seats": self.adapter.seats})
                ):
                    raise ValueError("Player left or request expired during validation")
                state = json.loads(
                    (self.adapter.root / "world/gamenight/status.json").read_text(
                        encoding="utf8"
                    )
                )
                if state["revision"] != self.request["expected_revision"]:
                    raise ValueError("World changed during mod validation")
            except Exception as e:
                self.result(False, str(e))
                return
            req = self.request
            prepared, active = (
                dict(self.adapter.prepare, seats=list(self.adapter.seats)),
                self.adapter.active,
            )
            checkpoint = self.adapter.root / "checkpoints" / str(uuid.UUID(req["id"]))
            marker = self.adapter.directory / "mod-install.json"
            try:
                staged, digest = modding.stage(self.adapter.root, req["values"])
                self.adapter.dispose()
                self.adapter.server.stop()
                shutil.copytree(self.adapter.root / "world", checkpoint)
                pending_marker = marker.with_suffix(".tmp")
                pending_marker.write_text(
                    json.dumps({"checkpoint": str(checkpoint), "id": req["id"]}),
                    encoding="utf8",
                )
                pending_marker.replace(marker)
            except Exception as e:
                # No live mod files have changed yet. In particular, a full disk
                # during checkpoint creation must not strand a stopped session.
                self.adapter.server.start()
                if self.adapter.session is None:
                    self.adapter.receive(prepared)
                self.adapter.resume_when_ready = active
                self.result(
                    False, "Could not save a checkpoint; mod not installed: " + str(e)
                )
                return
            try:
                shutil.copytree(
                    staged,
                    self.adapter.root / "world/worldmods/gamenight_custom",
                    dirs_exist_ok=True,
                )
                mt = self.adapter.root / "world/world.mt"
                if "load_mod_gamenight_custom" not in mt.read_text(encoding="utf8"):
                    mt.write_text(
                        mt.read_text(encoding="utf8")
                        + "\nload_mod_gamenight_custom = true\n",
                        encoding="utf8",
                    )
                (self.adapter.root / "world/gamenight/mod-current.json").write_text(
                    json.dumps(
                        {
                            "sha256": digest,
                            "values": req["values"],
                            "request_id": req["id"],
                            "previous_values": None
                            if req.get("undo")
                            else (state.get("mod_values") or {"bounce": 0}),
                        }
                    ),
                    encoding="utf8",
                )
                self.adapter.server.start()
                self.adapter.receive(prepared)
                self.future = None
                self.restart = active
            except Exception as e:
                self.adapter.server.stop()
                # Preserve the failed world for diagnosis. No recursive deletion.
                failed = self.adapter.root / ("failed-mod-" + str(uuid.UUID(req["id"])))
                preserve_world(self.adapter.root, failed.name)
                shutil.copytree(checkpoint, self.adapter.root / "world")
                self.adapter.server.start()
                self.adapter.receive(prepared)
                self.adapter.resume_when_ready = active
                self.result(
                    False, "Mod restart failed; saved world restored: " + str(e)
                )
                marker.unlink(missing_ok=True)
