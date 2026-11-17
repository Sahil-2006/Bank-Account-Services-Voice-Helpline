"""Replay the local deterministic suite; Studio scenario simulation is separate."""
import argparse
import hashlib
import json
from pathlib import Path
from .catalog import CASES, ROOT, ROWS
from helpline.desk import Desk
from helpline.policy import TERMS

CALENDAR = {"england-and-wales":{"events":[{"date":"2026-12-25"},{"date":"2027-01-01"}]}}

def run(c, desk_type=Desk):
    audit = []
    desk = desk_type(ROWS,calendar=lambda: CALENDAR if c["calendar"]=="ok" else {},callback=audit.append)
    replies = [desk.turn(turn) for turn in c["turns"]]
    last = replies[-1]
    transfer = desk.s["handoff"]
    checks = {
        "message":last==c["expected"] if c["exact"] else c["expected"].lower() in last.lower(),
        "reason":transfer.get("reason","")==c["reason"],
        "intent":desk.s["intent_tag"]==c["intent"],
        "channel":transfer.get("channel","")==c["channel"],
        "callback":audit==([transfer] if transfer else []),
        "disclaimer":sum(r.count(TERMS) for r in replies)==int(bool(c["channel"])),
        "tool":not c["tool"] or c["tool"] in desk.trace,
        "no_early_money":not any("rupees" in r for r in replies[:3] if c["record"] is not None),
    }
    return {"id":c["id"],"story":c["story"],"title":c["title"],"passed":all(checks.values()),
            "failed":[k for k,v in checks.items() if not v],"actual":last,"handoff":transfer,
            "tool_calls":desk.trace}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    results=[run(c) for c in CASES]
    data={"execution":"local deterministic transcript replay","cases_sha256":hashlib.sha256(json.dumps(CASES,sort_keys=True).encode()).hexdigest(),
          "total":len(results),"passed":sum(r["passed"] for r in results),"results":results}
    print(f"{data['passed']}/{data['total']} local transcript cases passed")
    for r in results:
        if not r["passed"]:
            print(r["id"],r["title"],r["failed"],r["actual"])
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    raise SystemExit(int(data["passed"]!=data["total"]))

if __name__=="__main__":
    main()
