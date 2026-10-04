"""Encode real renderer samples at their recorded wall-clock times."""
import argparse,csv,hashlib,json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw
import imageio_ffmpeg

p=argparse.ArgumentParser()
p.add_argument("--capture-root",type=Path,required=True)
p.add_argument("--output",type=Path,required=True)
p.add_argument("--takes",type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
shots=json.loads(a.takes.read_text())
segments=[];edl=[];contact=Image.new("RGB",(960,540))
for n,shot in enumerate(shots):
    folder=a.capture_root/shot["take"];seat=shot["seat"]
    samples=[(int(i),float(t)) for i,t in csv.reader((folder/f"seat-{seat}.csv").open())]
    start=shot["start"];length=shot["frames"]/30
    # Select the frame visible at each output time, without changing game speed.
    indices=[]
    for frame in range(shot["frames"]):
        target=start+frame/30
        index=max((i for i,t in samples if t<=target),default=samples[0][0])
        indices.append(index)
    concat=a.output/f"shot-{n}.txt"
    concat.write_text("".join("file '"+str((folder/f"seat-{seat}-{i:05}.jpg").resolve()).replace("\\","/")+"'\nduration 0.033333333333\n" for i in indices))
    segment=a.output/f"shot-{n}.mp4"
    subprocess.run([ffmpeg,"-v","error","-y","-f","concat","-safe","0","-i",str(concat),
        "-vf","scale=960:-2,crop=960:540:0:(ih-540)/2,setsar=1",
        "-r","30","-frames:v",str(shot["frames"]),"-an","-c:v","libx264","-crf","24",
        "-preset","slow","-pix_fmt","yuv420p","-color_range","tv",str(segment)],check=True)
    segments.append(segment)
    edl.append(dict(shot,source_in_frame=min(indices),source_out_frame=max(indices),unique_source_frames=len(set(indices))))
    for k in range(4):
        i=indices[min(len(indices)-1,k*len(indices)//4)]
        im=Image.open(folder/f"seat-{seat}-{i:05}.jpg").convert("RGB")
        im=im.resize((960,round(im.height*960/im.width)))
        top=(im.height-540)//2;im=im.crop((0,top,960,top+540)).resize((240,135))
        contact.paste(im,(k*240,n*135))
contact.save(a.output/"contact.jpg",quality=90)
concat=a.output/"segments.txt"
concat.write_text("".join("file '"+str(s.resolve()).replace("\\","/")+"'\n" for s in segments))
video=a.output/"mineclonia.mp4"
subprocess.run([ffmpeg,"-v","error","-y","-f","concat","-safe","0","-i",str(concat),
    "-c","copy","-movflags","+faststart",str(video)],check=True)
subprocess.run([ffmpeg,"-v","error","-y","-ss","3.6","-i",str(video),"-frames:v","1","-q:v","2",str(a.output/"mineclonia.jpg")],check=True)
hashes=subprocess.check_output([ffmpeg,"-v","error","-i",str(video),"-an","-f","framemd5","-"]).decode()
rows=[line for line in hashes.splitlines() if line and not line.startswith("#")]
report={"frames":len(rows),"distinct_decoded_frames":len(set(line.split(",")[-1].strip() for line in rows)),
        "width":960,"height":540,"fps":30,"duration":len(rows)/30,"shots":edl,
        "files":[{"file":f.name,"bytes":f.stat().st_size,"sha256":hashlib.sha256(f.read_bytes()).hexdigest()}
                 for f in (video,a.output/"mineclonia.jpg")]}
(a.output/"validation.json").write_text(json.dumps(report,indent=2))
(a.output/"SHA256SUMS.txt").write_text("".join(f'{x["sha256"]}  {x["file"]}\n' for x in report["files"]))
print(json.dumps(report))
assert len(rows)==150 and report["distinct_decoded_frames"]>=100,report
