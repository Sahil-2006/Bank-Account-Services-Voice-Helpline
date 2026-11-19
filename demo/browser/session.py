"""Browser bridge. Only packaged code from this repository is executed."""
import json
import re
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
                            "cases":[{
                                "id":result["id"], "title":result["title"],
                                "kind":definition["kind"], "story":result["story"],
                                "turns":definition["turns"], "expected":definition["expected"],
                                "reason":definition["reason"], "passed":result["passed"],
                                "failed":result["failed"], "actual":result["actual"]
                            } for definition, result in zip(CASES, cases)]})
        return json.dumps(results)
    if action == "catalog":
        return json.dumps([{
            "id":case["id"], "title":case["title"], "kind":case["kind"],
            "story":case["story"], "turns":case["turns"],
            "expected":case["expected"], "reason":case["reason"]
        } for case in CASES])
    if action == "demo_register":
        customer_id = text.strip().upper()
        if not desk.s.get("demo_record_ready") or not re.fullmatch(r"HTD-[A-F0-9]{12}",customer_id):
            raise ValueError("The demo profile could not be completed")
        desk.s.update(demo_customer_id=customer_id,demo_balance=0,demo_balance_active=True,
                      demo_record_ready=False,stage="demo_service",intent_tag="demo_account_opening")
        return json.dumps({"reply":"Demo customer ID: "+customer_id+". Your simulated demo balance starts at 0 rupees. You can check the balance, make a simulated deposit or withdrawal, or say finish.",
                           "handoff":desk.s["handoff"],"stage":desk.s["stage"],"private":False,
                           "unrecognized":False,"demoRecordReady":False})
    if action == "new":
        desk = new_call()
        reply = WELCOME
    elif action == "turn":
        before_stage = desk.s["stage"]
        reply = desk.turn(text)
        unrecognized = before_stage == "service" and reply.startswith("I didn't catch the request.")
        private = classify(text)=="private" or before_stage in {"open_name","open_phone","open_dob","open_aadhaar","open_pan"}
    else:
        raise ValueError("Unknown browser action")
    if action == "new":
        private = False
    return json.dumps({"reply":reply,"handoff":desk.s["handoff"],"stage":desk.s["stage"],"private":private,
                       "unrecognized":unrecognized,"demoRecordReady":desk.s.get("demo_record_ready",False)})
