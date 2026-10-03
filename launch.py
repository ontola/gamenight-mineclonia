"""Installed entrypoint: bundled Python, persistent saves outside the package."""
import argparse
import json
import logging
import os
from pathlib import Path
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    package = Path(__file__).resolve().parent.parent
    engine = package / "engine"
    if not (engine / "bin/luanti.exe").is_file():
        raise RuntimeError("The bundled Luanti engine is missing; reinstall this game.")
    os.environ["GAMENIGHT_MINECLONIA_ENGINE"] = str(engine)
    if args.self_test:
        from capabilities import SPECS
        import managed
        print(json.dumps({"ok": True, "settings": sorted(SPECS), "engine": str(engine)}))
        return 0
    if not os.environ.get("GAMENIGHT_TOKEN"):
        raise RuntimeError("Start Mineclonia from the GameNight game library.")
    root = args.data_dir or Path(os.environ["LOCALAPPDATA"]) / "GameNight/games/mineclonia"
    root = root.resolve()
    import managed
    sys.argv = [sys.argv[0], "--root", str(root), "--installed"]
    managed.main()
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GameNight/games/mineclonia"
        folder.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=folder / "launcher-error.log", level=logging.ERROR)
        logging.exception("Mineclonia could not start")
        raise
