"""Read physical SDL controllers and save evidence; never synthesize input."""

import argparse
import ctypes
import json
from pathlib import Path
import time

BUTTONS = (
    "A",
    "B",
    "X",
    "Y",
    "Back",
    "Guide",
    "Start",
    "Left stick",
    "Right stick",
    "LB",
    "RB",
    "D-pad up",
    "D-pad down",
    "D-pad left",
    "D-pad right",
)


def observe(package, seconds):
    sdl = ctypes.CDLL(str(package / "engine/bin/SDL2.dll"))
    sdl.SDL_SetHint.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    sdl.SDL_SetHint(b"SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", b"1")
    sdl.SDL_Init.argtypes = [ctypes.c_uint32]
    sdl.SDL_Init.restype = ctypes.c_int
    sdl.SDL_GameControllerOpen.argtypes = [ctypes.c_int]
    sdl.SDL_GameControllerOpen.restype = ctypes.c_void_p
    sdl.SDL_GameControllerName.argtypes = [ctypes.c_void_p]
    sdl.SDL_GameControllerName.restype = ctypes.c_char_p
    sdl.SDL_GameControllerGetAxis.argtypes = [ctypes.c_void_p, ctypes.c_int]
    sdl.SDL_GameControllerGetAxis.restype = ctypes.c_int16
    sdl.SDL_GameControllerGetButton.argtypes = [ctypes.c_void_p, ctypes.c_int]
    sdl.SDL_GameControllerGetButton.restype = ctypes.c_uint8
    sdl.SDL_GameControllerGetAttached.argtypes = [ctypes.c_void_p]
    sdl.SDL_GameControllerClose.argtypes = [ctypes.c_void_p]
    if sdl.SDL_Init(0x2000 | 0x200) != 0:
        raise RuntimeError("Could not initialize SDL controllers")
    handles, rows = [], []
    try:
        for i in range(sdl.SDL_NumJoysticks()):
            handle = sdl.SDL_GameControllerOpen(i)
            if handle:
                handles.append(handle)
                rows.append(
                    {
                        "device_index": i,
                        "name": sdl.SDL_GameControllerName(handle).decode("utf8"),
                        "buttons_seen": set(),
                        "axes_min": [32767] * 6,
                        "axes_max": [-32768] * 6,
                        "disconnected_samples": 0,
                    }
                )
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            sdl.SDL_GameControllerUpdate()
            for handle, row in zip(handles, rows):
                if not sdl.SDL_GameControllerGetAttached(handle):
                    row["disconnected_samples"] += 1
                    continue
                for i, name in enumerate(BUTTONS):
                    if sdl.SDL_GameControllerGetButton(handle, i):
                        row["buttons_seen"].add(name)
                for i in range(6):
                    value = sdl.SDL_GameControllerGetAxis(handle, i)
                    row["axes_min"][i] = min(row["axes_min"][i], value)
                    row["axes_max"][i] = max(row["axes_max"][i], value)
            time.sleep(0.01)
        for row in rows:
            row["buttons_seen"] = sorted(row["buttons_seen"])
        return {
            "seconds": seconds,
            "devices": rows,
            "limits": "Input observations only. Menu focus, game actions, reconnect recovery and comfort require an in-game playtest.",
        }
    finally:
        for handle in handles:
            sdl.SDL_GameControllerClose(handle)
        sdl.SDL_Quit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new evidence file")
    evidence = observe(args.package, args.seconds)
    args.output.write_text(json.dumps(evidence, indent=2), encoding="utf8")
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()
