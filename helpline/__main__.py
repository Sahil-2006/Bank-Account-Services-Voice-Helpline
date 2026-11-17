import argparse
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.request import urlopen
from .desk import Desk, WELCOME

ROOT = Path(__file__).resolve().parent
def calendar_feed():
    with urlopen("https://www.gov.uk/bank-holidays.json", timeout=4) as response:
        return json.load(response)

@contextmanager
def local_desk(state_dir):
    state_dir.mkdir(parents=True,exist_ok=True)
    db = sqlite3.connect(state_dir / "desk.sqlite3")
    db.execute("CREATE TABLE IF NOT EXISTS dispatches(customer TEXT, day TEXT, PRIMARY KEY(customer,day))")
    def reserve(customer,day):
        with db:
            return db.execute("INSERT OR IGNORE INTO dispatches VALUES (?,?)",(customer,day)).rowcount == 1
    def log(event):
        with (state_dir/"handoffs.jsonl").open("a",encoding="utf-8") as f:
            f.write(json.dumps(event)+"\n")
    desk = Desk(json.loads((ROOT/"fixtures.json").read_text()),calendar=calendar_feed,reserve=reserve,callback=log)
    try:
        yield desk
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Harbour Trust fictional voice desk text rehearsal")
    parser.add_argument("--state-dir",type=Path,default=Path(".local"))
    args = parser.parse_args()
    with local_desk(args.state_dir) as desk:
        print(WELCOME)
        try:
            while not desk.s["handoff"]:
                print(desk.turn(input("Caller> ")))
        except (EOFError,KeyboardInterrupt):
            pass

if __name__ == "__main__":
    main()
