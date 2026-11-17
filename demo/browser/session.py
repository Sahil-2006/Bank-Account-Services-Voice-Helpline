"""Browser bridge. Only packaged code from this repository is executed."""
import json
import sys
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, "/app")
from evaluation.catalog import CASES
from evaluation.run import run, CALENDAR
from helpline.desk import WELCOME
from helpline.policy import classify

def packaged_desk(version):
    archive = Path("/app/studio/packages") / f"HarbourTrust-{version}.zip"
    with ZipFile(archive) as bundle:
        path = next(p for p in bundle.namelist() if p.endswith("/tools/verify_identity/python_function/python_code.py"))
        module = {}
        exec(compile(bundle.read(path), path, "exec"), module)
    return module["Desk"], module["DIRECTORY"]

builds = {v: packaged_desk(v) for v in ("V1", "V2")}
dispatched = set()

def reserve(customer, day):
    key = (customer, day)
    if key in dispatched:
        return False
    dispatched.add(key)
    return True

def new_call():
    cls, records = builds["V2"]
    return cls(records, calendar=lambda: CALENDAR, reserve=reserve)

desk = new_call()

def respond(action, text):
    global desk
    if action == "suite":
        results = []
        for version, (cls, _) in builds.items():
            cases = [run(c, desk_type=cls) for c in CASES]
            results.append({"version":version,"total":len(cases),"passed":sum(c["passed"] for c in cases),
                            "failed":[{"id":c["id"],"title":c["title"],"actual":c["actual"]} for c in cases if not c["passed"]]})
        return json.dumps(results)
    if action == "new":
        desk = new_call()
        reply = WELCOME
    elif action == "turn":
        reply = desk.turn(text)
    else:
        raise ValueError("Unknown browser action")
    return json.dumps({"reply":reply,"handoff":desk.s["handoff"],"stage":desk.s["stage"],"private":classify(text)=="private"})
