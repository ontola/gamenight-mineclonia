"""Real local model/cloud/relay/Luanti check using the package test's scripted host.
No model outputs or host receipts are simulated. The test-only world probe arranges
players and selects a hotbar slot; uses arrive as actual controller frames.
"""

import json
from pathlib import Path
import shutil
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from host import Host
from prototype import read_json
import relay


def prepare_probe(root):
    """Install only in a disposable test world, before its server starts."""
    from runtime import prepare_data

    prepare_data(root)
    shutil.copytree(
        Path(__file__).parent / "test_fixtures/generated_probe",
        root / "world/worldmods/gamenight_generated_probe",
        dirs_exist_ok=True,
    )
    mt = root / "world/world.mt"
    content = mt.read_text(encoding="utf8")
    if "load_mod_gamenight_generated_probe" not in content:
        mt.write_text(
            content + "\nload_mod_gamenight_generated_probe = true\n", encoding="utf8"
        )


def run(root, fixture, session, roster, profiles, controls, send, pump, state):
    config = json.loads(fixture.read_text(encoding="utf8"))
    base = config["base"]
    token = config["account"]["token"]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def api(path, data=None, auth=token):
        request = urllib.request.Request(
            base + path,
            None if data is None else json.dumps(data).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + auth,
                "Origin": base,
            },
        )
        with opener.open(request, timeout=10) as response:
            body = response.read()
            return json.loads(body) if body else None

    class ScriptedHost:
        seats = staticmethod(Host.seats)

        def status(self):
            return {
                "seats": roster,
                "players": profiles,
                "library": [{"id": "mineclonia"}],
                "active_session": {
                    "id": session,
                    "game": "mineclonia",
                    "phase": "running",
                },
            }

    host = ScriptedHost()
    room = api("/v1/lobbies/register", {})
    receipt = None
    seen = {}
    pending = None
    worker = ThreadPoolExecutor(max_workers=1)
    rows = []
    checks = {}

    def poll():
        nonlocal receipt, pending
        if pending and pending.done():
            receipt = pending.result()
            pending = None
        snap = relay.snapshot(root, session, receipt, host, allow_loading=True)
        response = api("/v1/lobbies/poll", snap, room["token"])
        selection = response.get("selection")
        if selection and selection["id"] not in seen:
            seen[selection["id"]] = selection

            def execute():
                try:
                    return relay.execute(root, session, selection, host)
                except Exception as error:
                    return {
                        "id": selection["id"],
                        "ok": False,
                        "message": str(error)[:1000],
                    }

            pending = worker.submit(execute)

    def wait(seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            pump(0.2)
            poll()

    def request(text=None, values=None, action="mod"):
        poll()
        request_id = str(uuid.uuid4())
        if text:
            api(
                "/v1/rooms/agent",
                {"request_id": request_id, "text": text, "max_credits": 0},
            )
        else:
            api(
                "/v1/rooms/agent/control",
                {
                    "request_id": request_id,
                    "command": {
                        "action": action,
                        "instance": session,
                        "expected_revision": state()["revision"],
                        "values": values or {},
                    },
                },
            )
        started = time.monotonic()
        last = None
        while time.monotonic() - started < 1000:
            wait(0.3)
            data = api("/v1/rooms/agent")
            item = next((x for x in data["requests"] if x["id"] == request_id), None)
            if item and item["state"] != last:
                print("Generated mod request: " + item["state"], flush=True)
                last = item["state"]
            if item and item["state"] not in ("thinking", "queued"):
                row = {
                    "request": text or action,
                    "id": request_id,
                    "result": item,
                    "command": seen.get(request_id, {}).get("command"),
                    "seconds": round(time.monotonic() - started, 2),
                }
                rows.append(row)
                save()
                wait(0.7)
                return row
        raise TimeoutError("Generated mod request did not finish")

    def save():
        (root / "generated-report.json").write_text(
            json.dumps(
                {
                    "checks": checks,
                    "requests": rows,
                    "model": config.get("model", "configured local provider"),
                    "host": "scripted protocol host; real cloud/model/relay/package/server/clients",
                    "untested": [
                        "physical controllers",
                        "voice microphone capture",
                        "production deployment",
                    ],
                },
                indent=2,
            ),
            encoding="utf8",
        )

    def probe():
        return read_json(root / "world/gamenight/generated-probe.json")

    def arrange():
        (root / "world/gamenight/generated-probe-command.json").write_text(
            json.dumps({"arrange": True}), encoding="utf8"
        )
        wait(2)

    def use():
        before = probe()
        samples = []
        controls[0]["axes"][5] = 32767
        wait(0.15)
        controls[0]["axes"][5] = 0
        for _ in range(12):
            wait(0.15)
            samples.append(probe())
        return before, samples

    try:
        send({"type": "resume", "session": session})
        pump(1)
        poll()
        api("/v1/pairing/claim", api("/v1/lobbies/ticket", {"index": 0}, room["token"]))
        prompt = "Create a new Rally Wand item, stable ID rally, cyan color. Give each player one on joining. On use launch OTHER players within 4 blocks straight up with velocity y=12, leaving the wielder alone. Use a 1-second per-wielder cooldown. Persist a counter under key boosts for teammates launched and report it with gn.emit('boosts', count), including at startup. Add a pure logic self-test. This is new Lua content, not a scalar setting."
        first = request(prompt)
        for attempt in range(3):
            if first["result"]["state"] == "complete":
                code = first["command"]["values"]["code"]
                assert "gn.tool" in code and len(code) > 200
                checks["model_generated_new_tool"] = True
                startup_events = state()["generated_mod"].get("events") or {}
                arrange()
                before, samples = use()
                # A stale probe is a harness/server failure, never a model failure.
                assert abs(before["players"]["Couch1"]["position"]["x"]) < 0.25, (
                    "Player arrangement did not reach the server"
                )
                generated = state()["generated_mod"]
                events = generated.get("events") or {}
                checks["real_controller_use_launches_teammate"] = (
                    max(s["players"]["Couch2"]["position"]["y"] for s in samples)
                    > before["players"]["Couch2"]["position"]["y"] + 1
                )
                checks["wielder_unchanged"] = (
                    max(
                        abs(
                            s["players"]["Couch1"]["position"]["y"]
                            - before["players"]["Couch1"]["position"]["y"]
                        )
                        for s in samples
                    )
                    < 0.25
                )
                boosts = events.get("boosts", 0)
                checks["persistent_counter_recorded"] = boosts >= 1
                checks["counter_reported_at_startup"] = "boosts" in startup_events
                if all(checks.values()) and not generated.get("error"):
                    break
                diagnosis = str(
                    generated.get("error") or {k: v for k, v in checks.items() if not v}
                )
            else:
                diagnosis = first["result"].get("result", "Generation failed")
            assert attempt < 2, diagnosis
            first = request(
                "Repair the Rally Wand. Observed failure: "
                + diagnosis[:500]
                + ". Register all callbacks once at top level. Use one elapsed clock outside the tool callback for cooldowns. "
                "Emit the cumulative stored boosts counter at startup and after each use; never reset it. Keep the original mechanics: "
                + prompt
            )
            checks["repair_request_used"] = True
        assert all(checks.values()), checks
        pids = (root / "managed/view-pids.txt").read_text()
        revision = state()["revision"]
        broken = request(
            values={
                "title": "Invalid candidate",
                "code": code + "\nthis is invalid lua !!",
            }
        )
        checks["validation_failure_preserves_running_game"] = (
            broken["result"]["state"] == "failed"
            and (root / "managed/view-pids.txt").read_text() == pids
            and state()["revision"] == revision
            and state()["mod_values"]["code"] == code
        )
        assert checks["validation_failure_preserves_running_game"], broken
        second = request(
            "Modify our existing Rally Wand: keep the same item ID rally, cooldown and persistent boosts counter. Change the color to orange. On use launch nearby teammates with vertical velocity 6 AND horizontal velocity equal to the wielder's look direction x/z times 8. Still leave the wielder alone. Preserve the counter across restarts and report it on startup."
        )
        assert second["result"]["state"] == "complete", second
        code2 = second["command"]["values"]["code"]
        checks["followup_changes_generated_source"] = code2 != code
        checks["counter_survives_followup_restart"] = (
            state()["generated_mod"]["events"].get("boosts", 0) == boosts
        )
        arrange()
        before, samples = use()
        moved = max(
            sum(
                (
                    s["players"]["Couch2"]["position"][k]
                    - before["players"]["Couch2"]["position"][k]
                )
                ** 2
                for k in ("x", "z")
            )
            ** 0.5
            for s in samples
        )
        checks["followup_changes_real_trajectory"] = moved > 1
        checks["two_profiles_reconnected"] = len(state()["players"]) == 2 and all(
            p["profile"]["skin_applied"] for p in state()["players"]
        )
        assert all(checks.values()), checks
        count = state()["generated_mod"]["events"]["boosts"]
        undone = request(action="undo_mod")
        checks["undo_restores_previous_source"] = (
            undone["result"]["state"] == "complete"
            and state()["mod_values"]["code"] == code
        )
        checks["counter_survives_undo_restart"] = (
            state()["generated_mod"]["events"].get("boosts") == count
        )
        arrange()
        before, samples = use()
        checks["undo_restores_vertical_behavior"] = (
            max(s["players"]["Couch2"]["position"]["y"] for s in samples)
            > before["players"]["Couch2"]["position"]["y"] + 1
            and max(
                abs(
                    s["players"]["Couch2"]["position"]["z"]
                    - before["players"]["Couch2"]["position"]["z"]
                )
                for s in samples
            )
            < 0.5
        )
        checks["generated_runtime_healthy"] = state()["generated_mod"]["enabled"]
        assert all(checks.values()), checks
        print("Generated mod end-to-end checks passed", flush=True)
        print("Keeping the phone and game preview active for 120 seconds", flush=True)
        wait(120)
        return checks
    finally:
        controls[0]["axes"][5] = 0
        save()
        worker.shutdown(wait=True, cancel_futures=True)
