"""Build a Windows candidate from pinned sources; publishing is separate."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent

def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)

def main():
    cache = Path(sys.argv[1]).resolve()
    cache.mkdir(parents=True, exist_ok=False)
    lock = json.loads((ROOT / "sources.lock.json").read_text())
    archives = {}
    for name in ("python", "mineclonia"):
        spec = lock[name]
        path = cache / (name + ".zip")
        with urllib.request.urlopen(spec["url"], timeout=60) as response, path.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
            raise RuntimeError(name + " archive hash mismatch")
        archives[name] = path
    engine = cache / "engine"
    run("git", "clone", "--no-checkout", lock["engine"]["repository"], engine)
    run("git", "-C", engine, "checkout", "--detach", lock["engine"]["revision"])
    run("bash", engine / "gamenight/build-windows.sh", cache / "engine-build")
    compiler = cache / "engine-build/toolchain/bin/x86_64-w64-mingw32-gcc"
    launcher = cache / "Mineclonia.exe"
    run(compiler, "-municode", "-mwindows", "-Os", ROOT / "launcher.c", "-o", launcher)
    packages = list((cache / "engine-build/build/build").glob("luanti-*-win64.zip"))
    if len(packages) != 1:
        raise RuntimeError("Expected one engine archive")
    run(sys.executable, ROOT / "package.py",
        "--engine-zip", packages[0], "--engine-revision", lock["engine"]["revision"],
        "--python-zip", archives["python"], "--python-sha256", lock["python"]["sha256"],
        "--mineclonia-zip", archives["mineclonia"], "--launcher", launcher,
        "--output", cache / "mineclonia-windows.zip")

if __name__ == "__main__":
    main()
