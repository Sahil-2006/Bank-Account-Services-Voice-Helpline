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
       "date":"On what date will you make the transfer?",
       "open_name":"For this demo only, what fictional full name should I use?",
       "open_phone":"For this demo only, enter the sample phone number 0000000000.",
       "open_dob":"For this demo only, what fictional date of birth should I use?",
       "open_aadhaar":"Aadhaar verification is simulated. Say ‘demo verified’; do not share an Aadhaar number.",
       "open_pan":"PAN verification is simulated. Say ‘demo verified’; do not share a PAN number.",
       "open_confirm":"I have the demo details. No personal details will be saved. Say yes to create a demo profile, or no to cancel.",
       "demo_service":"You can check your demo balance, make a simulated deposit or withdrawal, or say finish.",
       "demo_tx_amount":"What amount should I use for the simulated transaction? Enter a positive amount.",
       "demo_tx_confirm":"Confirm this simulated transaction? Say yes to apply it to the demo balance, or no to cancel."}
YES = {"yes","yeah","correct","that's right","right","yes please","that is correct"}
NO = {"no","incorrect","wrong","no thanks","no thank you"}
PAN_PRIVATE = "Please keep PAN numbers private. This demo simulates identity checks and does not need a PAN number."

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

def is_account_opening_request(text):
    return bool(re.search(r"\b(?:open|create|start|apply for|register for)\b.{0,40}\baccount\b|\baccount opening\b",text))

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
        s["demo_record_ready"] = False
        text = clean(raw).strip("!?")
        kind = classify(text)
        if kind in ("crisis","human"):
            if not s["intent_tag"]:
                s["intent_tag"] = intent_of(text)
            self.run_tool(finish,"human",kind)
            reply = CRISIS if kind == "crisis" else HUMAN
        elif kind == "private":
            reply = PAN_PRIVATE if re.search(r"\bpan\b",text) or re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]",text.upper()) else PRIVATE
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
        allowed.extend(Decimal(str(value)) for value in (s.get("demo_balance"),s.get("demo_tx_amount")) if value not in (None,""))
        return safe_output(reply,allowed)

    def process(self,text):
        s = self.s
        stage = s["stage"]
        if stage in ("id","dob","ending","confirm_id"):
            return self.identity(stage,text)
        if stage in ("demo_service","demo_tx_amount","demo_tx_confirm"):
            return self.demo_balance_turn(stage,text)
        if stage.startswith("open_"):
            return self.open_demo_profile(stage,text)
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
            if intent == "balance" and s.get("demo_balance_active"):
                return "Your simulated balance is "+str(s["demo_balance"])+" rupees. No real funds are held here."
            if intent in ("deposit","withdraw"):
                from .tools import check_status
                self.trace.append("check_status")
                if not check_status(s,row):
                    return self.deliver()
                s.update(intent_tag="demo_"+intent,demo_balance=Decimal(str(row.get("balance") or 0)),
                         demo_balance_active=True,demo_tx_amount="",demo_return_stage="service",stage="demo_tx_amount")
                action = "deposit" if intent == "deposit" else "withdraw"
                return "This is a simulated "+action+" on the fictional account only. No real money moves. "+current_prompt(s)
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
            if is_account_opening_request(text):
                s.update(stage="open_name",intent_tag="demo_account_opening")
                return ("I can guide you through a simulated Harbour Trust account opening. Use fictional details only. "
                        "Do not enter real Aadhaar, PAN, phone, or birth-date information. "+current_prompt(s))
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

    def open_demo_profile(self,stage,text):
        s = self.s
        if stage == "open_name":
            if len(text) >= 2 and re.search(r"[^\W\d_]",text,re.UNICODE):
                s["stage"] = "open_phone"
        elif stage == "open_phone":
            if compact_digits(text) == "0000000000":
                s["stage"] = "open_dob"
            else:
                return "Use only the fictional sample number 0000000000. No phone number is retained. "+current_prompt(s)
        elif stage == "open_dob":
            if parse_day(text):
                s["stage"] = "open_aadhaar"
            else:
                return "Please give a fictional date, for example 1 January 1900. It is used only for this simulated check. "+current_prompt(s)
        elif stage in ("open_aadhaar","open_pan"):
            if clean(text).strip(".! ") in ("demo verified","verified","skip"):
                s["stage"] = "open_pan" if stage == "open_aadhaar" else "open_confirm"
            else:
                return "For the simulation, say ‘demo verified’. Never share an Aadhaar or PAN number. "+current_prompt(s)
        elif stage == "open_confirm":
            if text in YES:
                s["stage"] = "demo_service"
                s["demo_record_ready"] = True
                s["demo_balance_active"] = True
                return "Your simulated profile is ready. A demo customer ID will be assigned now. No real bank account or KYC application has been created."
            if text in NO:
                s.update(stage="id",intent_tag="",demo_record_ready=False)
                return "No problem. The demo profile was cancelled. "+WELCOME
        return current_prompt(s)

    def demo_balance_turn(self,stage,text):
        s = self.s
        if stage == "demo_service":
            intent = intent_of(text)
            if intent == "balance":
                return "Your simulated demo balance is " + str(s["demo_balance"]) + " rupees. No real funds are held here."
            if intent in ("deposit","withdraw"):
                s.update(intent_tag="demo_"+intent,demo_tx_amount="",demo_return_stage="demo_service",stage="demo_tx_amount")
                action = "deposit" if intent == "deposit" else "withdraw"
                return "A simulated "+action+" only changes the balance in this browser session. No real money moves. "+current_prompt(s)
            if re.search(r"\b(?:finish|done|exit|stop)\b",text):
                s["stage"] = "closed"
                return "Demo session ended. This was not a real bank account or transaction."
            return "You can check the demo balance, make a simulated deposit or withdrawal, or say finish."
        if stage == "demo_tx_amount":
            amount_text = text.lower().replace("rupees","").replace("rupee","").strip()
            amount = positive(amount_text)
            if amount is None:
                spoken = spoken_int(amount_text)
                amount = Decimal(spoken) if spoken is not None and spoken > 0 else None
            if amount is None or amount > Decimal("1000000"):
                return "That amount is outside the demo range. Enter a positive amount. "+current_prompt(s)
            s.update(demo_tx_amount=amount,stage="demo_tx_confirm")
            return "I heard a simulated "+s["intent_tag"].removeprefix("demo_")+" of "+str(amount)+" rupees. "+current_prompt(s)
        if stage == "demo_tx_confirm":
            return_stage = s.get("demo_return_stage","demo_service")
            return_intent = "demo_account_opening" if return_stage == "demo_service" else ""
            if text in NO:
                s.update(demo_tx_amount="",intent_tag=return_intent,stage=return_stage)
                return "Cancelled. Your demo balance is unchanged. " + current_prompt(s)
            if text in YES:
                amount = Decimal(str(s["demo_tx_amount"]))
                if s["intent_tag"] == "demo_withdraw" and amount > Decimal(str(s["demo_balance"])):
                    s.update(demo_tx_amount="",intent_tag=return_intent,stage=return_stage)
                    return "There are not enough simulated funds. Your demo balance is "+str(s["demo_balance"])+" rupees. " + current_prompt(s)
                if s["intent_tag"] == "demo_deposit":
                    s["demo_balance"] = Decimal(str(s["demo_balance"])) + amount
                    verb = "deposit"
                else:
                    s["demo_balance"] = Decimal(str(s["demo_balance"])) - amount
                    verb = "withdrawal"
                new_balance = s["demo_balance"]
                s.update(demo_tx_amount="",intent_tag=return_intent,stage=return_stage)
                return "Simulated "+verb+" recorded. Your demo balance is "+str(new_balance)+" rupees. No real money moved. "+current_prompt(s)
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
