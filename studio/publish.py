"""Import both builds and run hosted Evaluate using the signed-in gcloud account."""
import argparse
import base64
import io
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile, ZIP_DEFLATED
from .build import build, evaluation
from evaluation.catalog import CASES, ROOT

class Client:
    def __init__(self,p,region):
        self.project=p
        self.base="https://ces."+region+".rep.googleapis.com/v1beta/"
        self.cli=shutil.which("gcloud.cmd") or shutil.which("gcloud")
        self.token=""
        self.refresh()
    def refresh(self):
        self.token=subprocess.check_output([self.cli,"auth","print-access-token","--quiet"],text=True).strip()
    def call(self,method,path,data=None):
        for attempt in range(2):
            req=Request(self.base+path,method=method,data=json.dumps(data).encode() if data is not None else None,
                headers={"Authorization":"Bearer "+self.token,"x-goog-user-project":self.project,"Content-Type":"application/json"})
            try:
                with urlopen(req,timeout=90) as r:return json.load(r)
            except HTTPError as e:
                if e.code==401 and attempt==0:
                    self.refresh()
                    continue
                body=json.loads(e.read()).get("error",{})
                raise RuntimeError(f"CES HTTP {e.code}: {body.get('message',e.reason)}") from None
    def all(self,path,key):
        result=[];token=""
        while True:
            params={"pageSize":100}
            if token:params["pageToken"]=token
            r=self.call("GET",path+"?"+urlencode(params))
            result.extend(r.get(key,[]));token=r.get("nextPageToken","")
            if not token:return result
    def wait(self,operation):
        if "/operations/" not in operation.get("name",""):
            return operation
        while not operation.get("done"):
            time.sleep(8)
            operation=self.call("GET",operation["name"])
        if operation.get("error"):
            raise RuntimeError(json.dumps(operation["error"]))
        return operation.get("response",{})
def strip_evals(path):
    stream=io.BytesIO()
    with ZipFile(path) as orig, ZipFile(stream,"w",ZIP_DEFLATED) as target:
        for f in orig.namelist():
            if "/evaluations/" not in f:target.writestr(f,orig.read(f))
    return base64.b64encode(stream.getvalue()).decode()
def resolve_links(value,tools,agents):
    if isinstance(value,list):return [resolve_links(x,tools,agents) for x in value]
    if not isinstance(value,dict):return value
    d={}
    for key,v in value.items():
        if key=="tool" and isinstance(v,str):
            v=tools[v]
        elif key=="targetAgent":
            v=agents[v]
        d[key]=resolve_links(v,tools,agents)
    return d
def run(args):
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]",args.project):raise ValueError("Invalid project ID")
    client=Client(args.project,args.region)
    parent=f"projects/{args.project}/locations/{args.region}"
    client.call("GET",parent+"/apps?pageSize=1")
    if args.preflight:
        print("CES project access confirmed.")
        return
    if not args.team or not args.team.isdigit():raise ValueError("Specify the real team number with --team")
    display="Team"+args.team+" Harbour Trust Voice Desk"
    child="Team"+args.team+" Account Service"
    evidence=ROOT/".local"/"studio"/args.project/args.region/("team"+args.team)
    evidence.mkdir(parents=True,exist_ok=True)
    checkpoint=evidence/"progress.json"
    state=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
    def save():
        pending=checkpoint.with_suffix(".tmp")
        pending.write_text(json.dumps(state,indent=2),encoding="utf-8");pending.replace(checkpoint)
    def operation(key,method,path,body):
        if key not in state:
            state[key]=client.call(method,path,body)
            save()
        value=client.wait(state[key])
        state[key]=value
        save()
        return value
    with tempfile.TemporaryDirectory() as work:
        for version in ("V1","V2"):
            label="Team"+args.team+"-"+version
            path=Path(work)/(version+".zip")
            build(args.team,version,path)
            if version=="V1":
                body={"appContent":strip_evals(path),"displayName":display}
                # No appId: importing cannot overwrite another application.
                obj=operation("initial_import","POST",parent+"/apps:importApp",body)
                app=obj["name"]
                for w in obj.get("warnings",[]):print("Import warning:",w)
            else:
                app=state["initial_import"]["name"]
                # Update only the Python functions inside our own imported app.
                names={r["displayName"]:r["name"] for r in client.all(app+"/tools","tools")}
                with ZipFile(path) as bundle:
                    for f in bundle.namelist():
                        if "/tools/" not in f or not f.endswith(".json"):continue
                        t=json.loads(bundle.read(f))
                        if "pythonFunction" not in t:continue
                        code=t["pythonFunction"].copy()
                        code["pythonCode"]=bundle.read(display+"/"+code["pythonCode"]).decode()
                        client.call("PATCH",names[t["displayName"]]+"?updateMask=pythonFunction",{"pythonFunction":code})
            tools={r["displayName"]:r["name"] for r in client.all(app+"/tools","tools")}
            agents={r["displayName"]:r["name"] for r in client.all(app+"/agents","agents")}
            existing={r["displayName"]:r["name"] for r in client.all(app+"/evaluations","evaluations")}
            selected=[]
            for case in CASES:
                resource=evaluation(case,child)
                n=resource["displayName"]
                if n not in existing:
                    payload=resolve_links(resource,tools,agents)
                    existing[n]=client.call("POST",app+"/evaluations",payload)["name"]
                selected.append(existing[n])
            # Make only the external calendar deterministic in the evaluated snapshot.
            cal=tools["uk_bank_holidays"]
            client.call("PATCH",cal+"?updateMask=toolFakeConfig.enableFakeMode",{"toolFakeConfig":{"enableFakeMode":True}})
            versions={v["displayName"]:v for v in client.all(app+"/versions","versions")}
            version_obj=versions.get(label) or client.call("POST",app+"/versions",{"displayName":label,"description":"Capstone 10 regression build"})
            operation(label+"_operation","POST",app+":runEvaluation",{"appVersion":version_obj["name"],"evaluations":selected,"displayName":label+" full suite","runCount":1})
            runs=[r for r in client.all(app+"/evaluationRuns","evaluationRuns") if r.get("appVersion")==version_obj["name"]]
            (evidence/(label+"-runs.json")).write_text(json.dumps(runs,indent=2),encoding="utf-8")
            print(label,version_obj["name"],"run records",len(runs))
        client.call("PATCH",cal+"?updateMask=toolFakeConfig.enableFakeMode",{"toolFakeConfig":{"enableFakeMode":False}})
        print("Studio application:",app)
        print("Run evidence:",evidence)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",required=True);p.add_argument("--region",choices=("us","eu"),default="us")
    p.add_argument("--team");p.add_argument("--preflight",action="store_true")
    try:run(p.parse_args())
    except (ValueError,RuntimeError,HTTPError) as e:p.exit(1,str(e)+"\n")
