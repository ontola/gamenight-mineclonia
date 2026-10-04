"""Installed engine and persistent world paths; prototype defaults remain usable."""
import json
import os
from pathlib import Path
import secrets
import socket

def engine_path(root):
    override = os.environ.get("GAMENIGHT_MINECLONIA_ENGINE")
    return Path(override).resolve() if override else root / "controller-engine-managed"

def connection(root):
    path = root / "connection.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf8"))
    return {"port": 30123, "password": "local-isolated-test"}

def prepare_data(root):
    root.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    old = connection(root) if (root / "connection.json").exists() else {}
    info = {"port": port, "password": old.get("password") or secrets.token_urlsafe(24)}
    (root / "connection.json").write_text(json.dumps(info), encoding="utf8")
    world = root / "world"
    world.mkdir(exist_ok=True)
    mt = world / "world.mt"
    if not mt.exists():
        mt.write_text("gameid = mineclonia\nbackend = sqlite3\nplayer_backend = sqlite3\nauth_backend = sqlite3\nmod_storage_backend = sqlite3\nload_mod_gamenight_bridge = true\n", encoding="utf8")
    seed = root / "world-seed.txt"
    if not seed.exists():
        seed.write_text(str(secrets.randbits(63)), encoding="ascii")
    (root / "server.conf").write_text(
        "bind_address = 127.0.0.1\nserver_announce = false\nmax_users = 4\n"
        "default_privs = interact,shout\ncreative_mode = false\nenable_damage = false\n"
        "mg_name = v7\ngamenight_safe_spawn = true\n"
        + f"port = {port}\nfixed_map_seed = {seed.read_text().strip()}\n", encoding="utf8")
    return info
