"""Persistent profile ownership of world accounts, independent of controller seats.

Legacy Couch accounts are claimed once, without renaming any player database or
mod-storage keys. The registry lives inside the world so checkpoints include it.
"""

import hashlib
import json
import os
import re

ACCOUNT = re.compile(r"(?:Couch[1-4]|GN_[0-9a-f]{24})\Z")


def player_id(seat):
    occupant = seat.get("occupant", {})
    if occupant.get("kind") != "local":
        return None
    value = occupant.get("player_id")
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError("A local player needs a stable GameNight profile ID")
    return value


def accounts(root, seats):
    ids = [player_id(seat) for seat in seats]
    occupied = [value for value in ids if value is not None]
    if len(set(occupied)) != len(occupied):
        raise ValueError("Each local seat needs a different player profile")
    target = root / "world/gamenight/identities.json"
    if target.exists():
        record = json.loads(target.read_text(encoding="utf8"))
        mapping = record.get("profiles")
        if record.get("version") != 1 or not isinstance(mapping, dict):
            raise ValueError(
                "Invalid profile ownership registry; preserve the world for recovery"
            )
        if any(
            not isinstance(k, str)
            or not k
            or not isinstance(v, str)
            or not ACCOUNT.fullmatch(v)
            for k, v in mapping.items()
        ):
            raise ValueError("Invalid saved player account")
        if len(set(mapping.values())) != len(mapping):
            raise ValueError("A saved account belongs to more than one profile")
    else:
        mapping = {}
    original = dict(mapping)
    used = set(mapping.values())
    result = {}
    for seat, profile_id in zip(seats, ids):
        if profile_id is None:
            result[seat["index"]] = "Preview"
            continue
        if profile_id not in mapping:
            legacy = f"Couch{seat['index'] + 1}"
            account = (
                legacy
                if legacy not in used
                else "GN_" + hashlib.sha256(profile_id.encode()).hexdigest()[:24]
            )
            if account in used:
                raise ValueError(
                    "Player account collision; preserve the ownership registry"
                )
            mapping[profile_id] = account
            used.add(account)
        result[seat["index"]] = mapping[profile_id]
    if mapping != original:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Persist ownership before starting clients. A failed launch can retry
        # safely; an existing account must never be reassigned to someone else.
        temp = target.with_suffix(".tmp")
        with temp.open("w", encoding="utf8") as output:
            json.dump({"version": 1, "profiles": mapping}, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        temp.replace(target)
    return result
