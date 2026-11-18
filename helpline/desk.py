"""Conversation controller. Only synthetic directory records reach this module."""
import re
from datetime import date, datetime
from decimal import Decimal
from .speech import date_words, spoken_int
from .policy import (ADVICE, CRISIS, HUMAN, OUTSIDE, PRIVATE, SAFE, TERMS, as_digits, classify, clean,
                     compact_digits, intent_of, number_tokens, positive, safe_output, uk_advisory)
from .tools import (check_limit, complete_handoff, finish, fresh, human_message, lookup_account,
                    quote_balance, quote_statement, verify_caller)

WELCOME = "Welcome to Harbour Trust. What is your customer ID?"
MENU = "Would you like your balance, a statement, or a transfer limit?"
ASK = {"id":"What is your customer ID?", "dob":"What is your date of birth?", "ending":"What are the last four account digits?",
       "service":MENU, "months":"How many months should the statement cover?", "delivery":"Would you like a digital or printed copy?",
       "amount":"What transfer amount should I check, or should I just read the limit?", "channel":"Which transfer channel will you use?",
       "date":"On what date will you make the transfer?"}
YES = {"yes","yeah","correct","that's right","right","yes please","that is correct"}
NO = {"no","incorrect","wrong","no thanks","no thank you"}

def parse_day(text):
    for fmt in ("%Y-%m-%d","%d/%m/%Y","%d %B %Y","%B %d %Y","%d %b %Y"):
        try:
            return datetime.strptime(text.replace(",","").strip(),fmt).date().isoformat()
        except ValueError:
            pass
    normalized = date_words(text)
    if normalized:
        try:
            return date.fromisoformat(normalized).isoformat()
        except ValueError:
            pass
    return ""

def period_value(text):
    t = clean(text).replace(" and a half",".5")
    for w,n in {"twelve":"12","thirty six":"36","three":"3","six":"6","one":"1"}.items():
        t = re.sub(r"\b"+w+r"\b", n, t)
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*(?:months?)?[.!]?",t.replace(" .","."))
    return m.group(1) if m and positive(m.group(1)) else ""

def current_prompt(s):
    if s["stage"] == "confirm_id":
        return "I heard H T " + as_digits(s["candidate"][2:]) + ", ending " + as_digits(s["ending"]) + ". Is that right?"
    if s["stage"] == "confirm_period":
        return "You asked for " + s["period"] + " months. Is that right?"
    return ASK.get(s["stage"],MENU)

class Desk:
    def __init__(self, directory, state=None, calendar=None, reserve=None, callback=None):
        self.rows = directory
        self.s = state if state is not None else fresh()
        self.calendar = calendar
        self.reserve = reserve
        self.callback = callback
        self.trace = []

    def run_tool(self, func, *args):
        self.trace.append(func.__name__)
        return func(self.s, *args)

    def turn(self, raw):
        s = self.s
        if s["handoff"]:
            return "This call has ended."
        text = clean(raw).strip("!?")
        kind = classify(text)
        if kind in ("crisis","human"):
            if not s["intent_tag"]:
                s["intent_tag"] = intent_of(text)
            self.run_tool(finish,"human",kind)
            reply = CRISIS if kind == "crisis" else HUMAN
        elif kind == "private":
            reply = PRIVATE
        elif kind in ("prompt","harm"):
            reply = SAFE
            s["offered"] = True
        elif kind in ("advice","outside"):
            s["offered"] = True
            reply = ADVICE if kind == "advice" else OUTSIDE
        elif s["offered"] and text in YES:
            self.run_tool(finish,"human","accepted_offer")
            reply = HUMAN
        elif not text:
            reply = "Take your time. " + current_prompt(s)
        elif re.search(r"\b(?:what can you do|what services|what do you do)\b",text):
            reply = "I can check a balance, arrange a statement, or look up a transfer limit. " + current_prompt(s)
        else:
            if s["offered"] and text in NO:
                reply = current_prompt(s)
            else:
                reply = self.process(text)
            s["offered"] = False
        if s["handoff"] and self.callback:
            self.callback(dict(s["handoff"]))
        allowed = [Decimal(str(v)) for k,v in s["quote"].items() if k in ("balance","fee","limit")]
        return safe_output(reply,allowed)

    def process(self,text):
        s = self.s
        stage = s["stage"]
        if stage in ("id","dob","ending","confirm_id"):
            return self.identity(stage,text)
        if stage == "service":
            intent = intent_of(text)
            if not intent:
                s["unclear"] += 1
                if s["unclear"] >= 3:
                    self.run_tool(finish,"human","unclear_intent")
                    return HUMAN
                return "I didn't catch the request. " + MENU
            s["intent_tag"] = intent
            row = self.run_tool(lookup_account,self.rows)
            if not row:
                return self.deliver()
            if intent == "balance":
                self.run_tool(quote_balance,self.rows)
                return self.deliver()
            if intent in ("limit", "statement"):
                from .tools import check_status
                self.trace.append("check_status")
                if not check_status(s,row):
                    return self.deliver()
            s["stage"] = "months" if intent == "statement" else "channel"
        elif stage == "months":
            value = period_value(text)
            if value:
                s.update(period=value, stage="confirm_period")
        elif stage == "confirm_period":
            if text in YES:
                s["stage"] = "delivery"
            elif text in NO:
                s["stage"] = "months"
        elif stage == "delivery":
            medium = {"digital":"digital","email":"digital","printed":"printed","print":"printed","post":"printed"}.get(text,"")
            if medium:
                self.run_tool(quote_statement,self.rows,s["period"],medium)
                return self.deliver()
        elif stage == "channel":
            s.update(input_channel=text,stage="date")
        elif stage == "date":
            day = parse_day(text)
            if day:
                s.update(transfer_date=day,stage="amount")
        elif stage == "amount":
            value = text.replace("rupees","").strip()
            if value in ("limit only","just the limit","read the limit"):
                value = ""
            if value and positive(value) is None:
                n = spoken_int(value)
                if n is None or n <= 0:
                    return ASK["amount"]
                value = str(n)
            self.run_tool(check_limit,self.rows,value,s["input_channel"],s["transfer_date"])
            return self.deliver()
        return current_prompt(s)

    def identity(self,stage,text):
        s = self.s
        if stage == "id":
            if intent_of(text):
                s["intent_tag"] = intent_of(text)
            key = compact_digits(text).upper()
            if not re.fullmatch(r"HT\d{4}",key):
                if not intent_of(text) and self.invalid_identity_entry():
                    return HUMAN
                return "Please say H T followed by four digits."
            s.update(candidate=key,stage="dob")
        elif stage == "dob":
            day = parse_day(text)
            if day:
                next_stage = "confirm_id" if s.get("retry_stage") == "dob" and s.get("ending") else "ending"
                s.update(dob=day,stage=next_stage,retry_stage="")
            elif self.invalid_identity_entry():
                return HUMAN
        elif stage == "ending":
            tail = compact_digits(text)
            if re.fullmatch(r"\d{4}",tail):
                s.update(ending=tail,stage="confirm_id",retry_stage="")
            elif self.invalid_identity_entry():
                return HUMAN
        else:
            if text in NO:
                s.update(candidate="",ending="",dob="",retry_stage="",attempts=0,stage="id")
            elif text in YES:
                verification = self.run_tool(verify_caller,self.rows,s["candidate"],s["dob"],s["ending"])
                result = verification["result"]
                if result == "verified":
                    s.update(candidate="",dob="")
                    if s["intent_tag"]:
                        return self.process(s["intent_tag"])
                    return MENU
                if result == "human":
                    return HUMAN
                if result == "technical":
                    return human_message(s) + " " + HUMAN
                failed_fields = verification.get("failed_fields", [])
                retry = failed_fields[0] if failed_fields else "id"
                s[retry] = ""
                s.update(stage=retry,retry_stage=retry)
                return "I couldn't verify those details. " + ASK[retry]
        return current_prompt(s)

    def invalid_identity_entry(self):
        self.s["attempts"] += 1
        if self.s["attempts"] >= 3:
            self.run_tool(finish,"human","verification")
            return True
        return False

    def deliver(self):
        s = self.s
        if s["handoff"]:
            return (human_message(s) + " " + HUMAN).strip()
        q = s["quote"]
        if not s["pending"] or not q:
            return current_prompt(s)
        if "fee" in q and self.reserve and not self.reserve(s["customer_id"],s["now_override"][:10]):
            self.run_tool(finish,"human","already_sent")
            return human_message(s) + " " + HUMAN
        channel = s["pending"]["channel"]
        if "balance" in q:
            answer = "Your balance is " + str(q["balance"]) + " rupees."
        elif "fee" in q:
            answer = ("Your statement has no fee." if q["fee"] == 0 else "Your statement fee is " + str(q["fee"]) + " rupees.")
        else:
            answer = "Your daily limit is " + str(q["limit"]) + " rupees."
        if channel.startswith("BankWire") and self.calendar:
            try:
                feed = self.calendar()
            except Exception:
                feed = {}
            advisory = uk_advisory(s["pending"]["date"],feed)
            if advisory == "I couldn't check the UK clearing calendar.":
                self.run_tool(finish,"human","calendar")
                return (human_message(s) + " " + HUMAN).strip()
            answer += " " + advisory
        self.run_tool(complete_handoff)
        return answer + " " + TERMS + " Connecting you to " + channel + "."
