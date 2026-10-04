"""Observe the actual Windows package against a minimal scripted host.
This checks software behavior, not physical pads, speaker output or artwork.
"""

import argparse, hashlib, json, os, select, socket, subprocess, time, uuid
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--players", type=int, choices=range(1, 5), default=2)
    p.add_argument(
        "--hold",
        type=int,
        default=0,
        help="Seconds to keep views open for visual inspection",
    )
    p.add_argument("--benchmark-seconds", type=int, default=0)
    p.add_argument("--identity-test", action="store_true")
    p.add_argument("--mod-test", action="store_true")
    a = p.parse_args()
    if a.root.exists() and not a.resume:
        raise RuntimeError("Use a new probe directory")
    a.root.mkdir(parents=True, exist_ok=True)
    if not a.resume:
        (a.root / "world-seed.txt").write_text("gamenight-couch-prototype")
    results = {}
    from test_profiles import sample_players

    profiles = sample_players(a.players)
    roster = [
        {
            "index": i,
            "controller": "test-" + str(i),
            "occupant": {"kind": "local", "player_id": profiles[i]["id"]},
        }
        for i in range(a.players)
    ] + [
        {"index": i, "occupant": {"kind": "ai" if i == 3 else "empty"}}
        for i in range(a.players, 4)
    ]
    token = str(uuid.uuid4())
    session = str(uuid.uuid4())
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(20)
    env = dict(
        os.environ,
        GAMENIGHT="1",
        GAMENIGHT_ADDR="127.0.0.1:" + str(listener.getsockname()[1]),
        GAMENIGHT_GAME_ID="mineclonia",
        GAMENIGHT_TOKEN=token,
    )
    env.pop("GAMENIGHT_CAPTURE_ROOT", None)
    if a.benchmark_seconds:
        env["GAMENIGHT_BENCHMARK"] = "1"
    child = subprocess.Popen(
        [str(a.package / "Mineclonia.exe"), "--data-dir", str(a.root)], env=env
    )
    conn = None
    try:
        conn, _ = listener.accept()
        conn.setblocking(False)
        buffer = b""
        events = []
        controls = [
            {"controller": "test-" + str(i), "buttons": 0, "axes": [0] * 6}
            for i in range(a.players)
        ]

        def send(message):
            conn.sendall((json.dumps(message) + "\n").encode())

        def pump(seconds, until=None):
            nonlocal buffer
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                if results.get("prepare_rendered_views"):
                    send({"type": "controller_frame", "controllers": controls})
                readable, _, _ = select.select([conn], [], [], 0.016)
                if readable:
                    data = conn.recv(65536)
                    if not data:
                        raise RuntimeError("Package disconnected unexpectedly")
                    buffer += data
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        message = json.loads(line)
                        if message.get("type") == "hello":
                            if (
                                message.get("token") != token
                                or message.get("game") != "mineclonia"
                            ):
                                raise RuntimeError("Invalid package handshake")
                            results["authenticated_handshake"] = True
                            send(
                                {"type": "welcome", "protocol_version": 1, "party": {}}
                            )
                            send(
                                {
                                    "type": "prepare",
                                    "session": session,
                                    "seats": roster,
                                    "players": profiles,
                                }
                            )
                        events.append(
                            {k: v for k, v in message.items() if k != "token"}
                        )
                if until and until():
                    return
            if until:
                raise TimeoutError("Expected lifecycle event was not observed")

        def state():
            from prototype import read_json

            return read_json(a.root / "world/gamenight/status.json")

        pump(300, lambda: any(e.get("type") == "ready" for e in events))
        results["prepare_rendered_views"] = all(
            (a.root / f"managed/view-{i}.frame.ready").exists()
            for i in range(a.players)
        )
        send({"type": "start", "session": session})
        pump(4)
        before = state()
        results["profile_identity_and_skin_applied"] = all(
            p.get("profile", {}).get("name") == profiles[int(p["name"][-1]) - 1]["name"]
            and p["profile"]["color"] == profiles[int(p["name"][-1]) - 1]["color"]
            and p["profile"]["skin_applied"]
            and p["profile"]["hud"]
            for p in before["players"]
        )
        results["correct_player_count"] = len(before["players"]) == a.players
        ground = before["spawn_ground"]
        results["four_distinct_dry_spawns"] = (
            before["spawn_ready"]
            and len(ground) == 4
            and len({(p["x"], p["y"], p["z"]) for p in ground}) == 4
        )
        if not a.resume:
            results["new_players_near_verified_dry_spawns"] = all(
                any(
                    abs(player["position"]["x"] - p["x"]) < 1
                    and abs(player["position"]["z"] - p["z"]) < 1
                    and 0.4 <= player["position"]["y"] - p["y"] <= 1
                    for p in ground
                )
                for player in before["players"]
            )
        measurements = None
        if a.benchmark_seconds:
            from benchmark import measure

            measurements = measure(a.root, controls, pump, a.benchmark_seconds)
            (a.root / "benchmark.json").write_text(
                json.dumps(measurements, indent=2), encoding="utf8"
            )

        def position(snapshot, name):
            return next(p["position"] for p in snapshot["players"] if p["name"] == name)

        def distance(a, b):
            return sum((a[k] - b[k]) ** 2 for k in ("x", "z")) ** 0.5

        input_checks = []
        input_observations = []
        for i in range(a.players):
            pump(
                3
            )  # Let previous movement and any fall finish before testing another seat.
            previous = state()
            axis, value = [(0, -32768), (0, 32767), (1, 32767), (1, -32768)][i]
            controls[i]["axes"][axis] = value
            pump(0.6)
            controls[i]["axes"][axis] = 0
            pump(1)
            after = state()
            input_observations.append(
                [
                    distance(
                        position(previous, f"Couch{j + 1}"),
                        position(after, f"Couch{j + 1}"),
                    )
                    for j in range(a.players)
                ]
            )
            input_checks.append(
                distance(
                    position(previous, f"Couch{i + 1}"),
                    position(after, f"Couch{i + 1}"),
                )
                > 0.4
                and all(
                    distance(
                        position(previous, f"Couch{j + 1}"),
                        position(after, f"Couch{j + 1}"),
                    )
                    < 0.1
                    for j in range(a.players)
                    if j != i
                )
            )
        results["start_and_separate_scripted_input"] = all(input_checks)
        send({"type": "pause", "session": session})
        pump(1)
        paused = state()
        pump(2)
        results["pause_freezes_world"] = state()["game_time"] == paused["game_time"]
        profiles[0]["name"] = "Alex ★"
        profiles[0]["color"] = "#aa66dd"
        profiles[0]["avatar"] = profiles[-1]["avatar"]
        send(
            {
                "type": "party_updated",
                "session": session,
                "seats": roster,
                "players": list(reversed(profiles)),
            }
        )
        pump(1)
        updated = next(
            p["profile"] for p in state()["players"] if p["name"] == "Couch1"
        )
        results["profile_update_while_paused"] = (
            updated["name"] == "Alex ★"
            and updated["color"] == "#aa66dd"
            and updated["skin_applied"]
        )
        profiles = sample_players(a.players)
        send(
            {
                "type": "party_updated",
                "session": session,
                "seats": roster,
                "players": profiles,
            }
        )
        pump(1)
        if a.identity_test:
            import sqlite3

            def saved_players():
                with sqlite3.connect(
                    (a.root / "world/players.sqlite").as_uri() + "?mode=ro", uri=True
                ) as database:
                    return {
                        name: {
                            "position": (x, y, z),
                            "items": database.execute(
                                # Join by stable inventory name: Mineclonia reorders database IDs
                                # and regenerates the virtual mesh-hand/tool metadata at login.
                                # Carried items, crafting, equipment and every other list remain exact.
                                "SELECT v.inv_name, i.slot_id, i.item FROM player_inventory_items i "
                                "JOIN player_inventories v ON v.player=i.player AND v.inv_id=i.inv_id "
                                "WHERE i.player=? AND v.inv_name != 'hand' ORDER BY v.inv_name,i.slot_id",
                                (name,),
                            ).fetchall(),
                        }
                        for name, x, y, z in database.execute(
                            "SELECT name, posX, posY, posZ FROM player"
                        )
                    }

            def dispose():
                send({"type": "dispose", "session": session})
                pump(30, lambda: (a.root / "managed/view-pids.txt").read_text() == "")
                pump(1)

            def prepare(seats, people):
                count = sum(e.get("type") == "ready" for e in events)
                send(
                    {
                        "type": "prepare",
                        "session": session,
                        "seats": seats,
                        "players": people,
                    }
                )
                pump(180, lambda: sum(e.get("type") == "ready" for e in events) > count)
                pump(1)

            dispose()
            saved = saved_players()
            results["identity_fixture_contains_carried_items"] = all(
                any(
                    item
                    for name, slot, item in saved[f"Couch{i + 1}"]["items"]
                    if name == "main"
                )
                for i in range(a.players)
            )
            shuffled = [
                dict(seat, occupant=roster[a.players - 1 - i]["occupant"])
                for i, seat in enumerate(roster[: a.players])
            ]
            prepare(shuffled, profiles)
            results["seat_shuffle_keeps_profile_account"] = all(
                any(
                    player["name"] == f"Couch{i + 1}"
                    and player["profile"]["name"] == profiles[i]["name"]
                    for player in state()["players"]
                )
                for i in range(a.players)
            )
            dispose()
            changed = saved_players()
            (a.root / "identity-observations.json").write_text(
                json.dumps({"before": saved, "after_shuffle": changed}, indent=2),
                encoding="utf8",
            )
            results["seat_shuffle_preserves_inventory_and_position"] = all(
                saved[f"Couch{i + 1}"] == changed[f"Couch{i + 1}"]
                for i in range(a.players)
            )
            newcomer = dict(
                profiles[0], id="newcomer-maintenance-test", name="New player"
            )
            replacement = [
                dict(
                    shuffled[0], occupant={"kind": "local", "player_id": newcomer["id"]}
                )
            ] + shuffled[1:]
            prepare(shuffled, profiles)
            count = sum(e.get("type") == "ready" for e in events)
            send(
                {
                    "type": "party_updated",
                    "session": session,
                    "seats": replacement,
                    "players": profiles + [newcomer],
                }
            )
            pump(180, lambda: sum(e.get("type") == "ready" for e in events) > count)
            pump(1)
            results["replacement_profile_gets_own_account"] = any(
                player["name"].startswith("GN_")
                and player["profile"]["name"] == "New player"
                for player in state()["players"]
            )
            dispose()
            preserved = saved_players()
            (a.root / "identity-observations.json").write_text(
                json.dumps(
                    {
                        "before": saved,
                        "after_shuffle": changed,
                        "after_replace": preserved,
                    },
                    indent=2,
                ),
                encoding="utf8",
            )
            results["replacement_leaves_previous_inventory_intact"] = all(
                saved[f"Couch{i + 1}"] == preserved[f"Couch{i + 1}"]
                for i in range(a.players)
            )
            prepare(roster, profiles)
        send({"type": "resume", "session": session})
        pump(3)
        results["resume_advances_world"] = state()["game_time"] > paused["game_time"]
        if a.mod_test:
            from host import Host
            from prototype import read_json

            for undo, values in ((False, {"bounce": 1.5}), (True, {"bounce": 0})):
                request_id = str(uuid.uuid4())
                payload = {
                    "id": request_id,
                    "instance": session,
                    "expected_revision": state()["revision"],
                    "expires": time.time() + 180,
                    "seat": Host.seats({"seats": roster})[0],
                    "values": values,
                    "undo": undo,
                }
                pending = a.root / "managed/mod-request.tmp"
                pending.write_text(json.dumps(payload), encoding="utf8")
                pending.replace(pending.with_suffix(".json"))
                result_path = a.root / "managed/mod-result.json"

                def finished():
                    return (
                        result_path.exists()
                        and read_json(result_path).get("id") == request_id
                    )

                pump(240, finished)
                result = read_json(result_path)
                results["mod_undo_reconnects" if undo else "mod_install_reconnects"] = (
                    result["ok"]
                    and len(state()["players"]) == a.players
                    and state()["mod_values"] == values
                    and not (a.root / "managed/mod-install.json").exists()
                )
                if not result["ok"]:
                    raise RuntimeError(result["message"])
                pump(3)
        if a.hold:
            print(f"Holding {a.players} rendered views for inspection", flush=True)
            pump(a.hold)
        pids = [int(s) for s in (a.root / "managed/view-pids.txt").read_text().split()]
        pids.append(int((a.root / "managed/server.pid").read_text()))
        conn.close()
        conn = None
        results["host_disconnect_exits_entrypoint"] = child.wait(timeout=35) == 0
        import csv

        def alive(pid):
            output = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return any(
                len(row) > 1 and row[1] == str(pid)
                for row in csv.reader(output.splitlines())
            )

        results["host_disconnect_cleans_children"] = all(not alive(pid) for pid in pids)
        report = {
            "players": a.players,
            "package_sha256": hashlib.sha256(a.archive.read_bytes()).hexdigest(),
            "benchmark": measurements,
            "input_checks": input_checks,
            "input_observations": input_observations,
            "initial_world": before,
            "final_world": after,
            "build": json.loads((a.package / "BUILD.json").read_text()),
            "checks": results,
            "untested": [
                "physical controllers",
                "audio audibility",
                "cross-game switching",
            ],
        }
        (a.root / "report.json").write_text(json.dumps(report, indent=2))
        (a.root / "events.json").write_text(json.dumps(events, indent=2))
        print(json.dumps(results))
        if not all(results.values()):
            raise RuntimeError("A package observation failed")
    finally:
        if conn:
            conn.close()
        listener.close()
        if child.poll() is None:
            try:
                child.wait(timeout=35)
            except subprocess.TimeoutExpired:
                subprocess.run(
                    ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
                raise


if __name__ == "__main__":
    main()
