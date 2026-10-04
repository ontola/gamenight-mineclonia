"""Real engine test with a scripted GameNight adapter; no hardware-input claims."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid
from managed import Adapter
from runtime import prepare_data

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--engine",type=Path,required=True)
    p.add_argument("--seconds",type=int,default=600)
    p.add_argument("--resume",action="store_true",help="Reuse this explicitly selected test world")
    p.add_argument("--capture-root",type=Path)
    p.add_argument("--capture-mod",type=Path)
    p.add_argument("--players",type=int,choices=range(1,5),default=2)
    a=p.parse_args()
    if a.root.exists() and not a.resume:raise RuntimeError("Use a fresh playtest directory or --resume")
    a.root.mkdir(parents=True,exist_ok=True)
    for marker in ("stop","ready"):
        (a.root/marker).unlink(missing_ok=True)
    if a.capture_root:
        a.capture_root.mkdir(parents=True,exist_ok=True)
        os.environ["GAMENIGHT_CAPTURE_ROOT"]=str(a.capture_root.resolve())
    if a.capture_mod:
        import shutil
        shutil.copytree(a.capture_mod,a.root/"world/worldmods/gamenight_capture",dirs_exist_ok=True)
    os.environ["GAMENIGHT_MINECLONIA_ENGINE"]=str(a.engine.resolve())
    prepare_data(a.root)
    # Reproduce the old seed while requiring a verified dry spawn.
    seed=a.root/"world-seed.txt";seed.write_text("gamenight-couch-prototype")
    prepare_data(a.root)
    events=[]
    adapter=Adapter(a.root,lambda event:events.append(event))
    session=str(uuid.uuid4())
    seats=[{"index":i,"controller":f"test-{i}","occupant":{"kind":"local","player":f"test-player-{i}"}} for i in range(a.players)]
    adapter.receive({"type":"welcome"})
    adapter.receive({"type":"prepare","session":session,"seats":seats})
    control=a.root/"test-input.json"
    control.write_text(json.dumps({"buttons":[0]*a.players,"axes":[[0]*6 for _ in range(a.players)]}))
    started=False
    deadline=time.monotonic()+a.seconds
    try:
        while time.monotonic()<deadline and not (a.root/"stop").exists():
            try: payload=json.loads(control.read_text())
            except (OSError,json.JSONDecodeError):payload={"buttons":[0]*a.players,"axes":[[0]*6 for _ in range(a.players)]}
            adapter.receive({"type":"controller_frame","controllers":[{"controller":f"test-{i}","buttons":payload["buttons"][i],"axes":payload["axes"][i]} for i in range(a.players)]})
            adapter.tick()
            if adapter.ready and not started:
                adapter.receive({"type":"start","session":session})
                started=True
                (a.root/"ready").write_text(f"Real server and {a.players} rendered clients; scripted controller frames.")
            (a.root/"events.json").write_text(json.dumps(events))
            time.sleep(.016)
    finally:
        adapter.settings.close()
        adapter.mod_worker.shutdown(wait=True,cancel_futures=True)
        adapter.dispose()
        adapter.server.stop()
if __name__=="__main__":main()
