"""Persistent profile ownership of world accounts, independent of controller seats.

A player with a GameNight profile owns an account through their per-game
`profile_key`, so their inventory and position come back on later nights. A
guest has only the party's `player_id`, which lasts one party.

Legacy Couch accounts are claimed once, without renaming any player database or
mod-storage keys. Accounts saved under a party `player_id` before profile keys
existed are claimed once by the same player in that party, or by name. The
registry lives inside the world so checkpoints include it.
"""

import hashlib
import json
import os
import re

# Luanti PLAYERNAME_SIZE is 20; keep accounts below the launcher's 20-character truncation threshold.
ACCOUNT = re.compile(r"(?:Couch[1-4]|GN_[0-9a-f]{16})\Z")


def player_id(seat):
    occupant = seat.get("occupant", {})
    if occupant.get("kind") != "local":
        return None
    value = occupant.get("player_id")
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError("A local player needs a stable GameNight profile ID")
    return value


PROFILE_KEY = re.compile(r"[0-9a-f]{32}\Z")
PROFILE = "profile:"


def identity(seat, players):
    """The registry key for a seat: its profile when it has one."""
    value = player_id(seat)
    if value is None:
        return None
    for player in players:
        if isinstance(player, dict) and player.get("id") == value:
            key = player.get("profile_key")
            if isinstance(key, str) and PROFILE_KEY.fullmatch(key):
                return PROFILE + key
    return value


def _names(root):
    """Account -> player name, from the appearance file of the last session."""
    try:
        data = json.loads(
            (root / "world/gamenight/profiles.json").read_text(encoding="utf8")
        )
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        account: entry["name"]
        for account, entry in data.items()
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }


def _player_name(seat, players):
    value = player_id(seat)
    for player in players:
        if isinstance(player, dict) and player.get("id") == value:
            name = player.get("name")
            return name if isinstance(name, str) else None
    return None


def accounts(root, seats, players=()):
    raw = [player_id(seat) for seat in seats]
    ids = [identity(seat, players) for seat in seats]
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
    # A profile seen for the first time takes over the account it had under
    # its party player id, so nothing is lost when profile keys arrive.
    names = None
    for seat, profile_id, party_id in zip(seats, ids, raw):
        if profile_id is None or profile_id in mapping or profile_id == party_id:
            continue
        if party_id in mapping:
            mapping[profile_id] = mapping.pop(party_id)
            continue
        # Otherwise an account from an earlier night with this player's name,
        # if exactly one unclaimed one has it and nobody here is using it.
        if names is None:
            names = _names(root)
        name = _player_name(seat, players)
        busy = {mapping.get(other) for other in ids if other is not None}
        legacy = [
            key
            for key, account in mapping.items()
            if not key.startswith(PROFILE)
            and account not in busy
            and name
            and names.get(account) == name
        ]
        if len(legacy) == 1:
            mapping[profile_id] = mapping.pop(legacy[0])
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
                else "GN_" + hashlib.sha256(profile_id.encode()).hexdigest()[:16]
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
