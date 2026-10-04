"""Validate local seats and route opaque host controller tokens to frame files."""

import os
import time


def local_seats(seats):
    """Ignore empty/AI seats; keep stable host seat IDs and controller tokens."""
    result = [s for s in seats if s.get("occupant", {}).get("kind") == "local"]
    indices = [s["index"] for s in result]
    if len(result) > 4 or len(indices) != len(set(indices)):
        raise ValueError("Mineclonia supports at most four distinct local seats")
    if any(type(i) is not int or not 0 <= i < 4 for i in indices):
        raise ValueError("Invalid Mineclonia host seat index")
    return sorted(result, key=lambda s: s["index"])


def routed(seats, controllers):
    """Never interpret host tokens as SDL indexes, and never borrow a pad."""
    by_token = {p["controller"]: p for p in controllers}
    result = []
    used = set()
    for seat in seats:
        token = seat.get("controller")
        pad = by_token.get(token) if token and token not in used else None
        if token:
            used.add(token)
        if seat.get("occupant", {}).get("kind") != "local":
            pad = None
        axes = pad.get("axes") if pad else None
        buttons = pad.get("buttons") if pad else None
        valid = (
            isinstance(axes, list)
            and len(axes) == 6
            and all(type(v) is int and -32768 <= v <= 32767 for v in axes)
            and type(buttons) is int
            and 0 <= buttons < 16384
        )
        result.append(
            (True, buttons & ~(1 << 6), axes) if valid else (False, 0, [0] * 6)
        )
    return result


def publish(path, active, connected=False, buttons=0, axes=None):
    fields = [
        time.monotonic_ns(),
        int(active),
        int(connected),
        buttons,
        *(axes or [0] * 6),
    ]
    temp = path.with_suffix(".tmp")
    temp.write_text(" ".join(map(str, fields)), encoding="ascii")
    try:
        os.replace(temp, path)
    except PermissionError:
        pass  # reader is closing; the next frame replaces it
