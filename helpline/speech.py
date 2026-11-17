"""Normalize common English ASR forms at the point a date or amount is expected."""
import re

UNITS = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(),range(20)))
TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(),range(20,100,10)))
ORDINALS = "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth".split()
MONTHS = "january february march april may june july august september october november december".split()

def spoken_int(text):
    words=text.lower().replace("-"," ").replace(",","").split()
    total=part=0
    for word in words:
        if word == "and":
            continue
        if word in UNITS or word in TENS or word.isdigit():
            part+=int(word) if word.isdigit() else (UNITS.get(word) if word in UNITS else TENS[word])
        elif word == "hundred" and part:
            part*=100
        elif word in ("thousand","lakh") and part:
            total+=part*(1000 if word=="thousand" else 100000)
            part=0
        else:
            return None
    return total+part if words else None

def date_words(text):
    t=re.sub(r"(\d+)(st|nd|rd|th)\b",r"\1",text.lower())
    t=t.replace(","," ").replace("-"," ").replace("the ","").replace(" of "," ")
    for n,word in enumerate(ORDINALS,1):
        t=re.sub(r"\b"+word+r"\b",str(n),t)
    t=t.replace("thirtieth","30")
    parts=t.split()
    for i,month in enumerate(MONTHS,1):
        if month not in parts:
            continue
        m=parts.index(month)
        if m:
            day=spoken_int(" ".join(parts[:m]))
            year=parts[m+1:]
        else:
            if len(parts)<3:
                return ""
            count=2 if parts[1] in ("twenty","thirty") and len(parts)>3 and parts[2].isdigit() and int(parts[2])<10 else 1
            day=spoken_int(" ".join(parts[1:1+count]))
            year=parts[1+count:]
        if len(year)>1 and year[0] in ("nineteen","twenty") and "hundred" not in year:
            tail=spoken_int(" ".join(year[1:]))
            y=None if tail is None else UNITS.get(year[0],20)*100+tail
        else:
            y=spoken_int(" ".join(year))
        if day and y and 1000<=y<=9999:
            return f"{y:04d}-{i:02d}-{day:02d}"
    return ""
