"""Record one staged shot from the release renderer at natural wall-clock speed."""

import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prototype import command

p = argparse.ArgumentParser()
p.add_argument("--world-root", type=Path, required=True)
p.add_argument("--capture-root", type=Path, required=True)
p.add_argument("--shot", choices=["mine", "build", "blast", "bounce"], required=True)
p.add_argument("--take", type=int, default=1)
a = p.parse_args()
output = a.capture_root / (a.shot + "-" + str(a.take))
output.mkdir(parents=True, exist_ok=False)


def controls(axis=None, value=0):
    axes = [[0] * 6, [0] * 6]
    if axis is not None:
        axes[0][axis] = value
    (a.world_root / "test-input.json").write_text(
        json.dumps({"buttons": [0, 0], "axes": axes})
    )


def action(name):
    (a.world_root / "world/gamenight/capture-command.json").write_text(
        json.dumps({"action": name, "take": time.time_ns()})
    )


if a.shot == "bounce":
    result = command(a.world_root, "set", {"bounce": 0.5})
    if not result.get("ok"):
        raise RuntimeError(result)
controls()
time.sleep(1)  # Give the managed controller a neutral frame before recording.
(a.capture_root / "capture.txt").write_text(
    str(output.resolve()) + "\n" + ("0" if a.shot in ("mine", "build") else "1")
)
try:
    time.sleep(1.2)  # Let the first GPU readback finish while input is neutral.
    if a.shot == "mine":
        controls(5, 32767)
    elif a.shot == "build":
        controls(4, 32767)
    elif a.shot == "blast":
        action("ignite")
    elif a.shot == "bounce":
        action("bounce")
    time.sleep(7 if a.shot == "blast" else 4)
finally:
    controls()
    time.sleep(0.5)
    (a.capture_root / "capture.txt").write_text("")
(output / "take.json").write_text(
    json.dumps(
        {
            "shot": a.shot,
            "staged": True,
            "duration": "See per-view timestamp files",
            "action_after_seconds": 1.2,
        },
        indent=2,
    )
)
print(output)
