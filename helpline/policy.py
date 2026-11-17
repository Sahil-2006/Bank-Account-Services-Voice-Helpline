"""Deterministic rules shared by the local desk and the Studio tool builder."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING

NOW = "2026-11-10T09:00:00+05:30"
CRISIS = "I'm really sorry you're going through this. You are not alone, and help is available. If you are in immediate danger, please call 112 now. You can also call Tele-MANAS on 14416, free and open at all hours, to talk to a trained counsellor. I'm connecting you with a person now."
PRIVATE = "Please keep card, Aadhaar and PIN numbers private. I only need the requested verification details."
SAFE = "I can only share verified account information from our tools. Would you like a person?"
TERMS = "Limits and fees follow the bank's terms."
HUMAN = "I'm connecting you with a person now."
TECH = "I couldn't retrieve the account information."
ADVICE = "I can't give financial advice. Would you like a person?"
OUTSIDE = "I can help with bank account services. Would you like a person?"
DIGITS = "zero one two three four five six seven eight nine".split()
DIGIT_MAP = {**{word: str(i) for i, word in enumerate(DIGITS)}, "oh": "0"}
NOW_DAY = NOW[:10]

def clean(text):
    return " ".join(text.lower().replace("’", "'").strip().split())

def number_tokens(text):
    return re.sub(r"\b(" + "|".join(DIGIT_MAP) + r")\b", lambda m: DIGIT_MAP[m.group()], clean(text))

def compact_digits(text):
    return re.sub(r"[\s,.-]", "", number_tokens(text))

def classify(text):
    t = clean(text)
    if re.search(r"\b(?:suicidal|suicide|kill myself|end my life|hurt myself|harm myself|tak(?:e|ing) my own life|don't want to (?:live|be alive)|do not want to live|can't keep myself safe)\b", t):
        return "crisis"
    if re.search(r"\bhow (?:can|do) i (?:hurt|harm|attack) (?:someone|a person|people)\b", t):
        return "harm"
    if re.fullmatch(r"(?:please\s+)?(?:0|zero)[.!?]?", t) or re.search(r"\b(?:agent|representative|someone|human|real person|a person)\b", t):
        return "human"
    numbers = number_tokens(t)
    if re.search(r"(?<!\d)(?:\d[\s,-]*){12,}(?!\d)", numbers) or (re.search(r"\b(?:pin|card|aadhaar|aadhar)\b", t) and re.search(r"\d", numbers)):
        return "private"
    if re.search(r"\b(?:ignore|override|disregard)\b.*\b(?:instructions|rules|system)\b|\breveal (?:the |your )?system prompt\b", t):
        return "prompt"
    if re.search(r"\b(?:invest|investment advice|buy stocks|sell shares|which stock|best mutual fund|should i borrow)\b", t):
        return "advice"
    if re.search(r"\b(?:weather|recipe|pizza|football|flight|movie|train ticket)\b", t):
        return "outside"
    return ""

def intent_of(text):
    t = clean(text).strip(".!?")
    keypad = {"one":"balance","1":"balance","two":"statement","2":"statement","three":"limit","3":"limit"}
    found = [i for i, pattern in (("balance",r"\bbalance\b"),("statement",r"\bstatements?\b"),("limit",r"\blimits?\b")) if re.search(pattern,t)]
    return keypad.get(t, found[0] if len(found) == 1 else "")

def resolve_channel(name, transfer_date):
    try:
        day = date.fromisoformat(transfer_date)
    except (ValueError, TypeError):
        return ""
    cutover = date(2027, 1, 1)
    key = re.sub(r"[\s-]+", "", clean(name))
    if key == "instantpay":
        return "Instant Pay"
    if key in ("bankwire", "bankwireplus"):
        return "BankWire Plus" if day >= cutover else "BankWire"
    if key == "passbookexpress" and day < cutover:
        return "PassBook Express"
    return ""

def positive(value):
    try:
        n = Decimal(str(value).replace(",", "").strip())
        if n.is_finite() and n > 0:
            return n
    except (InvalidOperation, TypeError, ValueError):
        pass
    return None

def charge(months, delivery):
    n = positive(months)
    if n is None or delivery not in ("digital", "printed"):
        return {"error":"invalid"}
    if n > 36:
        return {"error":"archive"}
    rounded = int(n.to_integral_value(rounding=ROUND_CEILING))
    fees = ((0,100),(100,250),(300,500))
    tier = 0 if rounded <= 3 else (1 if rounded <= 12 else 2)
    return {"months":rounded, "fee":fees[tier][delivery == "printed"]}

def as_digits(value):
    return " ".join(DIGITS[int(c)] for c in value if c.isdigit())

def safe_output(text, allowed_money=()):
    if text == CRISIS:
        return text
    if re.search(r"(?:\d[\s,-]*){12,}",number_tokens(text)) or re.search(r"\b(?:you should (?:buy|invest|sell)|i recommend investing)\b",clean(text)):
        return SAFE
    numbers = number_tokens(text)
    if re.search(r"\b(?:account (?:number|ending)|account ends in)\D{0,12}(?:\d[\s-]*){5,}", numbers):
        return SAFE
    amounts = re.findall(r"\b([\d,]+(?:\.\d+)?)\s+rupees\b",text.lower())
    amounts += re.findall(r"(?:₹|\b(?:rs\.?|inr|rupees)\s+)\s*([\d,]+(?:\.\d+)?)",text.lower())
    if any(Decimal(v.replace(",", "")) not in allowed_money for v in amounts):
        return SAFE
    return text

def uk_advisory(day, data):
    """The fictional BankWire UK clearing leg uses England and Wales only."""
    try:
        target = date.fromisoformat(day)
        events = data["england-and-wales"]["events"]
        listed = {date.fromisoformat(event["date"]) for event in events}
        if target.year not in {d.year for d in listed}:
            raise ValueError("coverage")
        if target in listed or target.weekday() >= 5:
            return "UK clearing may be delayed by a weekend or bank holiday."
        return "The UK calendar shows a weekday with no listed bank holiday."
    except (KeyError, ValueError, TypeError):
        return "I couldn't check the UK clearing calendar."
