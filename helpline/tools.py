"""Rules take a server-owned session and the fictional directory as inputs."""
from .policy import NOW, TECH, as_digits, charge, compact_digits, positive, resolve_channel, clean

def fresh():
    return dict(verified=False, customer_id="", account_type="", intent_tag="", channel="",
                attempts=0, unclear=0, now_override=NOW, handoff={}, pending={}, quote={},
                stage="id", candidate="", ending="", dob="", period="", delivery="", offered=False)

def finish(s, destination, reason, channel=""):
    if not s["handoff"]:
        s["handoff"] = {"destination":destination, "reason":reason, "intent":s["intent_tag"], "channel":channel}
        s["stage"] = "closed"
        s["pending"] = {}
        s["dob"] = ""
        s["candidate"] = ""
    return s["handoff"]

def verify_caller(s, directory, customer_id, dob, last_four):
    if s["handoff"]:
        return {"result":"closed"}
    if s["verified"]:
        return {"result":"verified"}
    key = compact_digits(customer_id).upper()
    try:
        rows = [r for r in directory if r["id"] == key and r["dob"] == dob and r["last4"] == compact_digits(last_four)]
    except (OSError, TypeError, KeyError):
        finish(s,"human","lookup")
        return {"result":"technical"}
    s["attempts"] += 1
    if len(rows) == 1 and rows[0]["customer_status"] == "ACTIVE":
        s.update(verified=True, customer_id=key, ending=rows[0]["last4"], stage="service")
        return {"result":"verified"}
    if len(rows) == 1 and rows[0]["customer_status"] == "BLOCKED":
        finish(s,"human","restricted")
        return {"result":"human"}
    if s["attempts"] >= 3:
        finish(s,"human","verification")
        return {"result":"human"}
    return {"result":"retry"}

def lookup_account(s, directory):
    if not s["verified"] or s["handoff"]:
        return {}
    try:
        row = next((r for r in directory if r["id"] == s["customer_id"]), None)
    except (OSError, TypeError, KeyError):
        row = None
    if not row or not row.get("account"):
        finish(s,"human","lookup")
        return {}
    s["account_type"] = row["plan"] or ""
    return row

def check_status(s, row):
    if not row:
        return False
    if s["intent_tag"] != "statement" and row["status"] != "ACTIVE":
        reason = "status" if row["status"] in ("FROZEN","DORMANT") else "unknown_status"
        finish(s,"human",reason)
        return False
    return True

def quote_balance(s, rows):
    row = lookup_account(s, rows)
    if s["intent_tag"] != "balance" or not check_status(s, row):
        return {}
    if row["balance"] is None:
        finish(s,"human","lookup")
        return {}
    return prepare(s,row,{"balance":row["balance"]},row["channel"],s["now_override"][:10])

def quote_statement(s, rows, months, delivery, sent_today=False):
    row = lookup_account(s, rows)
    if not row or s["intent_tag"] != "statement":
        return {}
    if sent_today or row["last_sent"] == s["now_override"][:10]:
        finish(s,"human","already_sent")
        return {}
    q = charge(months,delivery)
    if q.get("error") == "archive":
        finish(s,"human","archive")
        return {}
    if "error" in q:
        return q
    q["delivery"] = delivery
    return prepare(s,row,q,row["channel"],s["now_override"][:10])

def check_limit(s, rows, amount, channel, transfer_date):
    row = lookup_account(s, rows)
    if s["intent_tag"] != "limit" or not check_status(s,row):
        return {}
    cap = {"Basic":25000, "Premium":100000}.get(row["plan"])
    if cap is None:
        finish(s,"human","unknown_plan")
        return {}
    if not resolve_channel(channel, transfer_date):
        finish(s,"human","unsupported_channel")
        return {}
    if amount != "" and positive(amount) is None:
        return {"error":"invalid"}
    if amount != "" and positive(amount) > cap:
        finish(s,"human","above_limit")
        return {}
    return prepare(s,row,{"limit":cap},channel,transfer_date)

def prepare(s,row,quote,channel,day):
    route = resolve_channel(channel or "",day)
    if not route:
        finish(s,"human","unsupported_channel")
        return {}
    s.update(channel=route,quote=quote,pending={"channel":route,"date":day})
    return quote

def complete_handoff(s):
    if s["verified"] and s["pending"] and s["quote"] and not s["handoff"]:
        return finish(s,"channel","service_complete",s["pending"]["channel"])
    return s["handoff"]

def human_message(s):
    from_reason = {"lookup":TECH,"unknown_status":TECH,"unknown_plan":TECH,
                   "already_sent":"A statement was already sent today.",
                   "archive":"This period needs help from a colleague.",
                   "above_limit":"That amount exceeds the daily limit.",
                   "unsupported_channel":"That channel is unavailable for this transfer.",
                   "status":"This account needs help from a colleague."}
    return from_reason.get(s["handoff"].get("reason"),"")
