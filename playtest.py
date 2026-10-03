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
    a=p.parse_args()
    if a.root.exists():raise RuntimeError("Use a fresh playtest directory")
    a.root.mkdir(parents=True)
    os.environ["GAMENIGHT_MINECLONIA_ENGINE"]=str(a.engine.resolve())
    prepare_data(a.root)
    # Reproduce the old seed while requiring a verified dry spawn.
    seed=a.root/"world-seed.txt";seed.write_text("gamenight-couch-prototype")
    prepare_data(a.root)
    events=[]
    adapter=Adapter(a.root,lambda event:events.append(event))
    session=str(uuid.uuid4())
    seats=[{"index":i,"controller":f"test-{i}","occupant":{"kind":"local","player":f"test-player-{i}"}} for i in range(2)]
    adapter.receive({"type":"welcome"})
    adapter.receive({"type":"prepare","session":session,"seats":seats})
    control=a.root/"test-input.json"
    control.write_text(json.dumps({"buttons":[0,0],"axes":[[0]*6,[0]*6]}))
    started=False
    deadline=time.monotonic()+a.seconds
    try:
        while time.monotonic()<deadline and not (a.root/"stop").exists():
            try: payload=json.loads(control.read_text())
            except (OSError,json.JSONDecodeError):payload={"buttons":[0,0],"axes":[[0]*6,[0]*6]}
            adapter.receive({"type":"controller_frame","controllers":[{"controller":f"test-{i}","buttons":payload["buttons"][i],"axes":payload["axes"][i]} for i in range(2)]})
            adapter.tick()
            if adapter.ready and not started:
                adapter.receive({"type":"start","session":session})
                started=True
                (a.root/"ready").write_text("Real server and two rendered clients; scripted controller frames.")
            (a.root/"events.json").write_text(json.dumps(events))
            time.sleep(.016)
    finally:
        adapter.settings.close()
        adapter.mod_worker.shutdown(wait=True,cancel_futures=True)
        adapter.dispose()
        adapter.server.stop()
if __name__=="__main__":main()
