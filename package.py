"""Create a self-contained Windows game ZIP from pinned component archives."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
MINECLONIA_SHA = "abeacf4e202d6e01a63119a36b46751eb6abfd42948a0b06e1ba8f63fb849e59"
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def extract(archive, target):
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if not (target/item.filename).resolve().is_relative_to(target.resolve()) or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Unsafe archive member")
        z.extractall(target)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engine-zip",type=Path,required=True)
    p.add_argument("--engine-revision",required=True)
    p.add_argument("--python-zip",type=Path,required=True)
    p.add_argument("--python-sha256",required=True)
    p.add_argument("--mineclonia-zip",type=Path,required=True)
    p.add_argument("--launcher",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if len(a.engine_revision)!=40 or any(c not in "0123456789abcdef" for c in a.engine_revision):
        raise ValueError("Pin a full engine source revision")
    if digest(a.mineclonia_zip)!=MINECLONIA_SHA:raise ValueError("Mineclonia archive hash mismatch")
    if digest(a.python_zip)!=a.python_sha256:raise ValueError("Python archive hash mismatch")
    if a.output.exists():raise ValueError("Preserve previous packages; choose a new output path")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        stage=Path(temp)
        extract(a.engine_zip,stage/"engine-unpack")
        engines=list((stage/"engine-unpack").glob("*/bin/luanti.exe"))
        if len(engines)!=1:raise ValueError("Expected one Windows engine")
        package=stage/"package";package.mkdir()
        shutil.move(str(engines[0].parent.parent),package/"engine")
        extract(a.mineclonia_zip,stage/"game-unpack")
        game=stage/"game-unpack/mineclonia"
        if not game.is_dir():raise ValueError("Mineclonia game missing")
        shutil.copytree(game,package/"engine/games/mineclonia")
        # Preserve upstream Mineclonia except for this explicit disconnect-race guard.
        patch=package/"engine/games/mineclonia/mods/CORE/mcl_init/outdated_warning.lua"
        source=patch.read_text(encoding="utf8")
        before="local current_protocol = core.get_player_information(pn).protocol_version"
        after="local info = core.get_player_information(pn)\n\tif not info then return end\n\tlocal current_protocol = info.protocol_version"
        if before not in source:raise ValueError("Upstream race-guard context changed")
        patch.write_text(source.replace(before,after),encoding="utf8")
        extract(a.python_zip,package/"python")
        pths=list((package/"python").glob("python*._pth"))
        if len(pths)!=1:raise ValueError("Expected an isolated embedded Python runtime")
        content=pths[0].read_text()
        pths[0].write_text(content+"\n../adapter\n",encoding="ascii")
        adapter=package/"adapter";adapter.mkdir()
        for item in ROOT.glob("*.py"):
            if not item.name.startswith("test_") and item.name not in ("package.py","playtest.py","build_release.py"):
                shutil.copy2(item,adapter/item.name)
        for name in ("mods",):shutil.copytree(ROOT/name,adapter/name)
        shutil.copy2(ROOT/"capabilities.json",adapter/"capabilities.json")
        shutil.copy2(a.launcher,package/"Mineclonia.exe")
        shutil.copy2(ROOT/"LICENSE",package/"ADAPTER-LICENSE.txt")
        shutil.copy2(ROOT/"README.md",package/"README.md")
        manifest={"format":1,"game":"mineclonia","engine_source":"https://github.com/ontola/luanti",
            "engine_revision":a.engine_revision,"engine_archive_sha256":digest(a.engine_zip),
            "mineclonia_version":"0.123.1","mineclonia_archive_sha256":MINECLONIA_SHA,
            "mineclonia_source":"https://codeberg.org/mineclonia/mineclonia/src/tag/0.123.1",
            "mineclonia_patch":"Guard a disconnected player's absent protocol information in mcl_init/outdated_warning.lua.",
            "python_archive":a.python_zip.name,"python_archive_sha256":digest(a.python_zip),
            "adapter_source":"https://github.com/ontola/gamenight-mineclonia",
            "adapter_revision":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
            "installed_bytes":sum(f.stat().st_size for f in package.rglob("*") if f.is_file())}
        (package/"BUILD.json").write_text(json.dumps(manifest,indent=2)+"\n")
        with zipfile.ZipFile(a.output,"x",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for item in sorted(package.rglob("*")):
                if not item.is_file():continue
                info=zipfile.ZipInfo(item.relative_to(package).as_posix(),(2026,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
                z.writestr(info,item.read_bytes())
    a.output.with_suffix(".sha256").write_text(digest(a.output)+"  "+a.output.name+"\n")
    print(json.dumps({"package":str(a.output),"sha256":digest(a.output),"bytes":a.output.stat().st_size}))
if __name__=="__main__":main()
