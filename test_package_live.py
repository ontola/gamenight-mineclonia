"""Observe the actual Windows package against a minimal scripted host.
This checks software behavior, not physical pads, speaker output or artwork.
"""
import argparse, hashlib, json, os, select, socket, subprocess, time, uuid
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--package",type=Path,required=True)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--resume",action="store_true")
    a=p.parse_args()
    if a.root.exists() and not a.resume:raise RuntimeError("Use a new probe directory")
    a.root.mkdir(parents=True,exist_ok=True)
    results={}
    token=str(uuid.uuid4());session=str(uuid.uuid4())
    listener=socket.socket();listener.bind(("127.0.0.1",0));listener.listen()
    listener.settimeout(20)
    env=dict(os.environ,GAMENIGHT="1",GAMENIGHT_ADDR="127.0.0.1:"+str(listener.getsockname()[1]),
        GAMENIGHT_GAME_ID="mineclonia",GAMENIGHT_TOKEN=token)
    env.pop("GAMENIGHT_CAPTURE_ROOT",None)
    child=subprocess.Popen([str(a.package/"Mineclonia.exe"),"--data-dir",str(a.root)],env=env)
    conn=None
    try:
        conn,_=listener.accept();conn.setblocking(False)
        buffer=b"";events=[]
        controls=[{"controller":"test-"+str(i),"buttons":0,"axes":[0]*6} for i in range(2)]
        def send(message):conn.sendall((json.dumps(message)+"\n").encode())
        def pump(seconds,until=None):
            nonlocal buffer
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if results.get("prepare_rendered_both_views"):
                    send({"type":"controller_frame","controllers":controls})
                readable,_,_=select.select([conn],[],[],.016)
                if readable:
                    data=conn.recv(65536)
                    if not data:raise RuntimeError("Package disconnected unexpectedly")
                    buffer+=data
                    while b"\n" in buffer:
                        line,buffer=buffer.split(b"\n",1)
                        message=json.loads(line)
                        if message.get("type")=="hello":
                            if message.get("token")!=token or message.get("game")!="mineclonia":
                                raise RuntimeError("Invalid package handshake")
                            results["authenticated_handshake"]=True
                            send({"type":"welcome","protocol_version":1,"party":{}})
                            send({"type":"prepare","session":session,"seats":[
                                {"index":i,"controller":"test-"+str(i),
                                 "occupant":{"kind":"local","player":str(uuid.uuid4())}} for i in range(2)]})
                        events.append({k:v for k,v in message.items() if k!="token"})
                if until and until():return
            if until:raise TimeoutError("Expected lifecycle event was not observed")
        def state():
            return json.loads((a.root/"world/gamenight/status.json").read_text())
        pump(180,lambda:any(e.get("type")=="ready" for e in events))
        results["prepare_rendered_both_views"]=all((a.root/f"managed/view-{i}.frame.ready").exists() for i in range(2))
        send({"type":"start","session":session})
        pump(4)
        before=state()
        controls[0]["axes"][1]=-32768
        pump(.6)
        controls[0]["axes"][1]=0
        pump(1)
        after=state()
        def position(snapshot,name):
            return next(p["position"] for p in snapshot["players"] if p["name"]==name)
        def distance(a,b):
            return sum((a[k]-b[k])**2 for k in ("x","z"))**.5
        results["start_and_separate_scripted_input"]=(
            distance(position(before,"Couch1"),position(after,"Couch1"))>.4 and
            distance(position(before,"Couch2"),position(after,"Couch2"))<.1)
        send({"type":"pause","session":session});pump(1)
        paused=state();pump(2)
        results["pause_freezes_world"]=state()["game_time"]==paused["game_time"]
        send({"type":"resume","session":session});pump(3)
        results["resume_advances_world"]=state()["game_time"]>paused["game_time"]
        pids=[int(s) for s in (a.root/"managed/view-pids.txt").read_text().split()]
        pids.append(int((a.root/"managed/server.pid").read_text()))
        conn.close();conn=None
        results["host_disconnect_exits_entrypoint"]=child.wait(timeout=35)==0
        import csv
        def alive(pid):
            output=subprocess.check_output(["tasklist","/FI",f"PID eq {pid}","/FO","CSV","/NH"],
                text=True,creationflags=subprocess.CREATE_NO_WINDOW)
            return any(len(row)>1 and row[1]==str(pid) for row in csv.reader(output.splitlines()))
        results["host_disconnect_cleans_children"]=all(not alive(pid) for pid in pids)
        report={"package_sha256":hashlib.sha256(a.archive.read_bytes()).hexdigest(),
            "build":json.loads((a.package/"BUILD.json").read_text()),"checks":results,
            "untested":["physical controllers","audio audibility","player profile appearance","cross-game switching"]}
        (a.root/"report.json").write_text(json.dumps(report,indent=2))
        (a.root/"events.json").write_text(json.dumps(events,indent=2))
        print(json.dumps(results))
        if not all(results.values()):raise RuntimeError("A package observation failed")
    finally:
        if conn:conn.close()
        listener.close()
        if child.poll() is None:
            try:child.wait(timeout=35)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill","/PID",str(child.pid),"/T","/F"],
                    creationflags=subprocess.CREATE_NO_WINDOW,check=False)
                raise
if __name__=="__main__":main()
