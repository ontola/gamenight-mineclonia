"""Real two-client engine check of the documented function dispatcher."""

import argparse, json, os, sys, time, uuid
from pathlib import Path

source = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(source))
from runtime import prepare_data
from server import Server
from views import ViewGroup
from identities import accounts
from profiles import publish as publish_profiles
from test_profiles import sample_players
from input_frames import publish
from prototype import command, read_json
from host import Host
import relay

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--root", type=Path, required=True, help="Fresh isolated world directory"
)
parser.add_argument(
    "--engine",
    type=Path,
    required=True,
    help="Engine directory containing bin/luanti.exe",
)
parser.add_argument(
    "--seed",
    default="2972258495425823389",
    help="Known dry-spawn seed used for verification",
)
args = parser.parse_args()
root = args.root
if root.exists():
    raise RuntimeError("Preserve previous test worlds; use a fresh root")
root.mkdir(parents=True)
os.environ["GAMENIGHT_MINECLONIA_ENGINE"] = str(args.engine.resolve())
(root / "world-seed.txt").write_text(args.seed)
prepare_data(root)
people = sample_players(2)
seats = [
    {
        "index": i,
        "controller": "function-test-" + str(i),
        "occupant": {"kind": "local", "player_id": p["id"]},
    }
    for i, p in enumerate(people)
]
names = accounts(root, seats)
publish_profiles(root, seats, people, names)
session = str(uuid.uuid4())


class ScriptedHost:
    seats = staticmethod(Host.seats)

    def status(self):
        return {
            "seats": seats,
            "players": people,
            "library": [{"id": "mineclonia"}],
            "active_session": {"id": session, "game": "mineclonia", "phase": "running"},
        }


host = ScriptedHost()
server = Server(root)
views = ViewGroup(root)
observations = []
try:
    print("Starting isolated Mineclonia world for game function checks.", flush=True)
    server.start()
    pid = server.process.pid
    views.launch(seats, names)

    def pump():
        (root / "managed/server.frame").write_text(
            f"{time.monotonic_ns()} 1 0 0 0 0 0 0 0 0"
        )
        for frame in views.frames:
            publish(frame, True, True, 0, [0] * 6)

    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        pump()
        state = read_json(root / "world/gamenight/status.json")
        if len(state.get("players") or []) == 2:
            break
        time.sleep(0.1)
    assert len(state.get("players") or []) == 2
    seat = host.seats(host.status())[1]
    print("Two real player clients connected.", flush=True)

    def call(name, args, request_id=None):
        pump()
        current = relay.snapshot(root, session, host=host)["discovery"]["controls"]
        selection = {
            "id": request_id or str(uuid.uuid4()),
            "game": "mineclonia",
            "seat": seat,
            "expires": time.time() + 60,
            "command": {
                "action": "call",
                "instance": session,
                "expected_revision": current["revision"],
                "values": {"name": name, "arguments": args},
            },
        }
        result = relay.execute(root, session, selection, host)
        observations.append({"function": name, "arguments": args, "result": result})
        assert result["ok"], result
        if current["game_api"]["functions"][name]["mutates"]:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                pump()
                if (
                    read_json(root / "world/gamenight/status.json")["revision"]
                    > current["revision"]
                ):
                    break
                time.sleep(0.05)
        return selection, result

    _, found = call("items.search", {"query": "diamond sword"})
    item = next(
        i["id"] for i in found["data"]["items"] if i["id"] == "mcl_tools:sword_diamond"
    )
    _, before = call("inventory.list", {"target": "all"})
    request_id = str(uuid.uuid4())
    selected, given = call(
        "inventory.give", {"target": "self", "item": item, "count": 2}, request_id
    )
    assert given["data"]["players"] == [
        {"player": names[1], "delivered": 2, "leftover": 0}
    ], given
    # Replaying the same admitted operation returns the durable receipt without another grant.
    replay = command(
        root,
        "call",
        dict(selected["command"]["values"], caller=names[1]),
        expected=selected["command"]["expected_revision"],
        request_id=request_id,
    )
    assert replay["ok"] and replay["result"] == given["data"]
    _, after = call("inventory.list", {"target": "all"})
    inventories = {p["player"]: p["items"] for p in after["data"]["players"]}
    old = {p["player"]: p["items"] for p in before["data"]["players"]}

    def quantity(items):
        return sum(i["count"] for i in (items or []) if i["item"] == item)

    assert quantity(inventories[names[1]]) == quantity(old[names[1]]) + 2
    assert inventories[names[0]] == old[names[0]]
    _, healed = call("players.heal", {"target": "self"})
    assert healed["data"][0]["hp"] == 20
    position = next(p["position"] for p in state["players"] if p["name"] == names[1])
    _, moved = call(
        "players.teleport",
        {
            "target": "self",
            "x": position["x"] + 1,
            "y": position["y"],
            "z": position["z"],
        },
    )
    _, observed = call("players.list", {})
    player = next(p for p in observed["data"] if p["player"] == names[1])
    assert abs(player["position"]["x"] - (position["x"] + 1)) < 0.2
    assert server.process.pid == pid and server.process.poll() is None
    report = {
        "ok": True,
        "engine_pid_unchanged": True,
        "two_real_clients": True,
        "duplicate_grant_did_not_repeat": True,
        "other_player_inventory_unchanged": True,
        "observations": observations,
        "limits": [
            "Scripted host seats and controller frames",
            "No real model or microphone in this engine check",
            "No store deployment",
        ],
    }
    (root / "functions-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf8"
    )
    print(
        "Passed: lookup, caller-scoped grant, inventory observation, replay, heal and teleport without restart.",
        flush=True,
    )
finally:
    (root / "function-observations.json").write_text(
        json.dumps(observations, indent=2), encoding="utf8"
    )
    views.close()
    server.stop()
