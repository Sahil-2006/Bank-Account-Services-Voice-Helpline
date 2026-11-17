"""Line-delimited JSON bridge for the Windows speech client."""
import json
import sys
from pathlib import Path
from .__main__ import local_desk
from .desk import WELCOME

def main():
    with local_desk(Path(".local")) as desk:
        print(json.dumps({"reply":WELCOME,"stage":"id"}),flush=True)
        for line in sys.stdin:
            reply=desk.turn(json.loads(line))
            print(json.dumps({"reply":reply,"stage":desk.s["stage"],"handoff":desk.s["handoff"]}),flush=True)
            if desk.s["handoff"]:
                break

if __name__=="__main__":
    main()
