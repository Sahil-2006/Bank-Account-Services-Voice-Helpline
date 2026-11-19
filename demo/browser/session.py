"""Browser bridge. Only packaged code from this repository is executed."""
import json
import sys
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, "/app")
from evaluation.catalog import CASES
from evaluation.run import run, CALENDAR
from helpline.desk import WELCOME
from helpline.policy import CALENDAR_CACHE, classify

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
    calendar_path = Path("/app/helpline/runtime-calendar.json")
    if calendar_path.exists():
        feed = json.loads(calendar_path.read_text())
    else:
        feed = {**CALENDAR_CACHE, "_source":"cache"}
    return cls(records, calendar=lambda: feed, reserve=reserve)

desk = new_call()

def respond(action, text):
    global desk
    unrecognized = False
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
        before_stage = desk.s["stage"]
        reply = desk.turn(text)
        unrecognized = before_stage == "service" and reply.startswith("I didn't catch the request.")
    else:
        raise ValueError("Unknown browser action")
    return json.dumps({"reply":reply,"handoff":desk.s["handoff"],"stage":desk.s["stage"],"private":classify(text)=="private","unrecognized":unrecognized})
