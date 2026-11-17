import argparse
import json
import sqlite3
from pathlib import Path
from urllib.request import urlopen
from .desk import Desk, WELCOME

ROOT = Path(__file__).resolve().parent
def calendar_feed():
    with urlopen("https://www.gov.uk/bank-holidays.json", timeout=4) as response:
        return json.load(response)

def main():
    parser = argparse.ArgumentParser(description="Harbour Trust fictional voice desk text rehearsal")
    parser.add_argument("--state-dir",type=Path,default=Path(".local"))
    args = parser.parse_args()
    args.state_dir.mkdir(parents=True,exist_ok=True)
    db = sqlite3.connect(args.state_dir / "desk.sqlite3")
    db.execute("CREATE TABLE IF NOT EXISTS dispatches(customer TEXT, day TEXT, PRIMARY KEY(customer,day))")
    def reserve(customer,day):
        with db:
            return db.execute("INSERT OR IGNORE INTO dispatches VALUES (?,?)",(customer,day)).rowcount == 1
    def log(event):
        with (args.state_dir/"handoffs.jsonl").open("a",encoding="utf-8") as f:
            f.write(json.dumps(event)+"\n")
    desk = Desk(json.loads((ROOT/"fixtures.json").read_text()),calendar=calendar_feed,reserve=reserve,callback=log)
    print(WELCOME)
    try:
        while not desk.s["handoff"]:
            print(desk.turn(input("Caller> ")))
    except (EOFError,KeyboardInterrupt):
        pass
    finally:
        db.close()

if __name__ == "__main__":
    main()
