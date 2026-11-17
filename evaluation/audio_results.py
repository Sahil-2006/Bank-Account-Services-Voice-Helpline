"""Feed recognized transcripts into the same desk used by the local voice client."""
import json
import sys
from pathlib import Path
from .catalog import ROOT,ROWS
from helpline.desk import Desk
from helpline.policy import CRISIS

def summarize(source):
    rows=json.loads(source.read_text(encoding="utf-8-sig"))
    byfile={r["file"]:r for r in rows if r["mode"]=="service vocabulary"}
    ids=[f"in-{i}.wav" for i in range(5)]
    plans=[
        ("Clean balance call",ids,"service_complete"),
        ("Noisy ID then clean retry",["noisy.wav"]+ids,"service_complete"),
        ("Interrupt with representative",ids[:2]+["overlap.wav"],"human"),
        ("Zero during statement",ids[:4]+["in-8.wav","in-5.wav"],"human"),
        ("Crisis at entry",["in-7.wav"],"crisis")]
    calls=[]
    for name,files,expected in plans:
        desk=Desk(ROWS);turns=[]
        for f in files:
            r=byfile[f]
            turns.append({"file":f,"said":r["said"],"heard":r["heard"],"reply":desk.turn(r["heard"])})
        passed=desk.s["handoff"].get("reason")==expected
        if expected=="crisis":
            passed=passed and turns[-1]["reply"]==CRISIS
        calls.append(dict(name=name,turns=turns,passed=passed,handoff=desk.s["handoff"]))
    out={"method":"Synthetic Windows speech synthesis to PCM, local Windows ASR and local desk. No cloud console or microphone was used.",
         "recognition":rows,"calls":calls}
    (ROOT/"evidence/local-audio.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    for c in calls:
        print(c["name"],c["passed"],c["turns"][-1]["heard"],c["handoff"])
if __name__=="__main__":
    summarize(Path(sys.argv[1]))
