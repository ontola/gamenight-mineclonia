"""Build pinned Windows packages, reusing verified engine component archives."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
ENGINE_RECIPE = 1


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def engine_key(spec):
    # The pinned commit includes build scripts, dependency versions and hashes.
    return hashlib.sha256(
        json.dumps({"engine": spec, "recipe": ENGINE_RECIPE}, sort_keys=True).encode()
    ).hexdigest()


def cached_engine(directory, spec):
    archive = directory / "engine.zip"
    manifest = directory / "engine.json"
    if not archive.exists() or not manifest.exists():
        return None
    metadata = json.loads(manifest.read_text(encoding="utf8"))
    if metadata.get("key") != engine_key(spec) or metadata.get("sha256") != digest(
        archive
    ):
        raise ValueError(
            "Cached engine does not match its pinned specification/checksum"
        )
    return archive


def download(spec, directory):
    path = directory / (spec["sha256"] + ".zip")
    if not path.exists():
        temporary = path.with_suffix(".partial")
        with (
            urllib.request.urlopen(spec["url"], timeout=60) as response,
            temporary.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
        if digest(temporary) != spec["sha256"]:
            raise ValueError("Downloaded component hash mismatch")
        temporary.replace(path)
    if digest(path) != spec["sha256"]:
        raise ValueError("Cached component hash mismatch")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--component-cache", type=Path)
    parser.add_argument("--launcher-compiler", default="x86_64-w64-mingw32-gcc")
    args = parser.parse_args()
    build = args.output.resolve()
    build.mkdir(parents=True, exist_ok=False)
    cache = (args.component_cache or build / "components").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / "sources.lock.json").read_text(encoding="utf8"))
    archives = {name: download(lock[name], cache) for name in ("python", "mineclonia")}
    component = cache / engine_key(lock["engine"])
    component.mkdir(exist_ok=True)
    engine_archive = cached_engine(component, lock["engine"])
    reused = engine_archive is not None
    if engine_archive is None:
        source = build / "engine"
        run("git", "clone", "--no-checkout", lock["engine"]["repository"], source)
        run("git", "-C", source, "checkout", "--detach", lock["engine"]["revision"])
        run("bash", source / "gamenight/build-windows.sh", build / "engine-build")
        candidates = list(
            (build / "engine-build/build/build").glob("luanti-*-win64.zip")
        )
        if len(candidates) != 1:
            raise RuntimeError("Expected one engine archive")
        engine_archive = component / "engine.zip"
        shutil.copy2(candidates[0], engine_archive)
        metadata = {
            "key": engine_key(lock["engine"]),
            "sha256": digest(engine_archive),
            "source": lock["engine"],
        }
        (component / "engine.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf8"
        )
    launcher = build / "Mineclonia.exe"
    run(
        args.launcher_compiler,
        "-municode",
        "-mwindows",
        "-Os",
        ROOT / "launcher.c",
        "-o",
        launcher,
    )
    run(
        sys.executable,
        ROOT / "package.py",
        "--engine-zip",
        engine_archive,
        "--engine-revision",
        lock["engine"]["revision"],
        "--python-zip",
        archives["python"],
        "--python-sha256",
        lock["python"]["sha256"],
        "--mineclonia-zip",
        archives["mineclonia"],
        "--launcher",
        launcher,
        "--output",
        build / "mineclonia-windows.zip",
    )
    report = {
        "engine_cache_hit": reused,
        "engine_key": engine_key(lock["engine"]),
        "engine_archive_sha256": digest(engine_archive),
    }
    (build / "build-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf8"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
