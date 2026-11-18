"""Create a CX Agent Studio JSON-format import archive with portable display-name links."""
import argparse
import ast
import json
import re
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from evaluation.catalog import CASES, ROOT, ROWS
from helpline.desk import Desk, MENU
from helpline.policy import CRISIS, PRIVATE, SAFE, TERMS
from helpline.tools import fresh
from evaluation.run import CALENDAR

TOOLS = {
    "verify_identity":("Collect and confirm the three identity fields. Use during all root verification steps.",("id","dob","ending","confirm_id")),
    "select_service":("Capture the intent from the latest caller turn and check the verified account. Return the next spoken response.",("service",)),
    "statement_service":("Confirm duration, determine delivery and quote the statement fee for a verified caller.",("months","confirm_period","delivery")),
    "limit_service":("Capture the channel, transfer date and amount and check the verified account's limit.",("channel","date","amount")),
}
VARS = {**fresh(),"transfer_date":"","input_channel":"","last_invocation":"","last_result":{},"logged":False,"calendar_unavailable":False}
GUARDS = [
 ("Private identifiers","contentFilter",{"matchType":"REGEXP_MATCH","bannedContentsInUserInput":[r"\b(?:[0-9][ ,\-]*){12,19}\b",r"(?i)\b(?:pin|aadhaar|aadhar|card)\b.{0,24}(?:[0-9]|zero|one|two|three|four|five|six|seven|eight|nine)"]},PRIVATE),
 ("Crisis support","llmPolicy",{"policyScope":"USER_QUERY","allowShortUtterance":True,"prompt":"Trigger for personal present danger of self-harm, suicidal intent or inability to stay safe, including paraphrases. Tiredness or frustration alone is insufficient."},CRISIS),
 ("Grounded account replies","llmPolicy",{"policyScope":"AGENT_RESPONSE","prompt":"Trigger when a reply gives financial advice, reads more than four digits of an account number or states an account amount, fee or limit unsupported by the latest verified tool result. Reading an approved crisis message, a date or a four-digit account ending is permitted."},SAFE),
 ("Harm safety","modelSafety",{"safetySettings":[{"category":"HARM_CATEGORY_DANGEROUS_CONTENT","threshold":"BLOCK_MEDIUM_AND_ABOVE"}]},SAFE),
 ("Prompt security","llmPromptSecurity",{"defaultSettings":{},"failOpen":False},SAFE),
]
AFTER = '''def after_tool_callback(tool, input, callback_context, tool_response):
    event = callback_context.variables.get("handoff", {})
    if event and not callback_context.variables.get("logged", False):
        print({"event": "handoff", "destination": event["destination"], "intent": event["intent"], "channel": event["channel"], "reason": event["reason"]})
        callback_context.variables["logged"] = True
    return None
'''
def terminal_callback():
    return '''def after_agent_callback(callback_context):
    parts = callback_context.get_last_agent_output() or []
    reply = " ".join(p.text for p in parts if getattr(p, "text", None)).strip()
    if reply != APPROVED:
        return None
    state = callback_context.variables
    event = {"destination":"human","reason":"crisis","intent":state.get("intent_tag",""),"channel":""}
    state["handoff"] = event
    state["stage"] = "closed"
    state["pending"] = {}
    state["dob"] = ""
    state["candidate"] = ""
    if not state.get("logged",False):
        print({"event":"handoff", **event})
        state["logged"] = True
    return None
'''.replace("APPROVED",repr(CRISIS))

def code_for(version):
    blocks=[]
    for file in (("policy.py","tools.py","desk.py") if version=="V1" else ("speech.py","policy.py","tools.py","desk.py")):
        path="helpline/"+file
        source = (subprocess.check_output(["git","show","local-v1:"+path],cwd=ROOT).decode() if version=="V1" else (ROOT/path).read_text(encoding="utf-8"))
        tree=ast.parse(source)
        # Standalone sandbox functions cannot import the repository package.
        class Strip(ast.NodeTransformer):
            def visit_ImportFrom(self,node):
                return None if node.level else node
        blocks.append(ast.unparse(Strip().visit(tree)))
    blocks.append("DIRECTORY = "+repr(ROWS))
    blocks.append((ROOT/"studio/runtime.py").read_text())
    return "\n\n".join(blocks)

def safe_readers():
    return {
       "lookup_verified_account":'''def lookup_verified_account() -> dict:
    """Look up only the authenticated account. Omit DOB, full identifiers and balances."""
    s = _session(context)
    row = lookup_account(s, DIRECTORY)
    return {"found": bool(row), "plan": row.get("plan", ""), "ending": row.get("last4", "")}
''',
       "read_account_status":'''def read_account_status() -> dict:
    """Read verified status before balance, statement or limit requests."""
    s = _session(context)
    row = lookup_account(s, DIRECTORY)
    return {"status": (row.get("status") or "UNKNOWN") if row and s["intent_tag"] in ("balance","statement","limit") else "UNAVAILABLE"}
'''}
def instruction(sub, team, child):
    shared = (
        "\nConstraints\nSpeak in short sentences. Speak an amount as rupees, dates naturally and ID digits in small groups. "
        "Never ask for card, Aadhaar, PIN or full account numbers. Say only approved tool facts. "
        "On silence gently repeat the active prompt. On barge-in stop speaking and listen. "
        "A request for a person or standalone zero is immediate. For crisis say exactly this and route to a person immediately:\n"+CRISIS+
        "\nHandle these interruptions using the current stage tool. Never repeat a disclaimer or continue a closed call. "
        "The logged handoff represents the fictional destination. Do not claim to have sent funds or opened a real bank connection.")
    if sub:
        return ("Role\nYou are the Harbour Trust Account Service desk.\nPersona\nCalm, concise and patient on a phone line.\n"
                "Context\nYou receive verified callers from the voice desk. Read {stage} and {intent_tag}. Every customer and queue is fictional.\n"
                "Task\nOn entry pass on an existing response if this turn was already handled. On a fresh service selection call {@TOOL: lookup_verified_account}, "
                "then {@TOOL: select_service}. For statements and confirmed balance or limit requests {@TOOL: read_account_status} is available for checking status. "
                "At months, confirm_period or delivery use {@TOOL: statement_service}. At channel, date or amount use {@TOOL: limit_service}. "
                "Use exactly one stage-changing tool per caller turn. Speak its say field. It handles the calendar and handoff internally. "
                "If lookup returns found false, still call select_service to record the technical handoff. Never ask a caller to invent missing values.\n"
                "Example\nCaller: two. Desk: How many months should the statement cover? Caller: twelve. Desk: You asked for twelve months. Is that right?"+shared)
    return ("Role\nYou are the Harbour Trust root voice desk.\nPersona\nPatient, discreet and warm.\n"
            "Context\nA fictional account holder is calling. {verified} and {stage} carry the trusted session state.\n"
            "Task\nStart with: Welcome to Harbour Trust. What is your customer ID? For each new caller turn use {@TOOL: verify_identity}. "
            "Speak the returned say field once. After verification route to {@AGENT: "+child+"}, forwarding the stage and existing reply. "
            "For a general service question give a one-sentence description and return to the prompt. Offer a person for off-topic requests or financial advice. "
            "Do not ask for confirmation of a human handoff.\nExample\nCaller: representative. Desk: I'm connecting you with a person now."+shared)

def advisory_spec():
    event={"type":"object","properties":{"date":{"type":"string","format":"date"},"title":{"type":"string"}}}
    region={"type":"object","properties":{"events":{"type":"array","items":event}}}
    return {"openapi":"3.0.3","info":{"title":"UK clearing calendar","version":"1.0"},
            "servers":[{"url":"https://www.gov.uk"}],"paths":{"/bank-holidays.json":{"get":{"operationId":"uk_bank_holidays",
            "description":"Return the public UK holiday calendar. Use England and Wales for the fictional BankWire clearing leg.",
            "responses":{"200":{"description":"UK divisions","content":{"application/json":{"schema":{"type":"object","properties":{"england-and-wales":region}}}}}}}}}}

def evaluation(c, child):
    title=c["id"]+" "+c["title"]
    m=lambda txt: {"role":"agent","chunks":[{"text":txt}]}
    summary=c["expected"]+". Routing reason "+(c["reason"] or "none")+". Intent "+(c["intent"] or "empty")+". Channel "+(c["channel"] or "empty")+"."
    resource={"displayName":title,"description":c["story"]+" | "+summary,"tags":[c["story"],c["kind"]]}
    if c["kind"]=="scenario":
        resource["scenario"]={"task":c["goal"]+". Use these fictional caller details and turns as guidance: "+" / ".join(c["turns"])+".",
             "maxTurns":max(8,len(c["turns"])+4),"rubrics":["The final response communicates: "+c["expected"],"The route and metadata match: "+summary,
             "The desk protects private details and speaks transfer terms only for a channel transfer."],
             "scenarioExpectations":[{"agentResponse":m(c["expected"])}]}
        if c["calendar"]=="unavailable":
            resource["scenario"]["variableOverrides"]={"calendar_unavailable":True}
    else:
        desk=Desk(ROWS,calendar=lambda:CALENDAR)
        turns=[]
        for t in c["turns"]:
            st=desk.s["stage"]
            verified=desk.s["verified"]
            reply=desk.turn(t)
            steps=[{"userInput":{"text":t}}]
            # Native guardrails can satisfy safety expectations without an ordinary tool call.
            if reply not in (CRISIS,PRIVATE,SAFE):
                tool=next((name for name,(_,stages) in TOOLS.items() if st in stages),None)
                if tool:
                    steps.append({"expectation":{"toolCall":{"tool":tool,"args":{}}}})
            if not verified and desk.s["verified"]:
                steps.append({"expectation":{"agentTransfer":{"targetAgent":child}}})
            steps.append({"expectation":{"agentResponse":m(reply),"comparisonType":"EQUALS" if reply in (CRISIS,PRIVATE) else "SEMANTIC_SIMILARITY"}})
            if desk.s["handoff"]:
                steps.append({"expectation":{"updatedVariables":{"handoff":desk.s["handoff"]},"comparisonType":"CONTAINS"}})
            turns.append({"steps":steps})
        resource["golden"]={"turns":turns}
    return resource

def build(team,version,out):
    prefix="Team"+team if team else "RosterPending"
    name=prefix+" Harbour Trust Voice Desk"
    child=prefix+" Account Service"
    resources={}
    def put(path,v):
        resources[path]=v if isinstance(v,str) else json.dumps(v,indent=2,ensure_ascii=False)
    def obj(group,display,value):
        slug=re.sub("[^a-zA-Z0-9_]+","_",display).strip("_")
        put(f"{group}/{slug}/{slug}.json",value)
    code=code_for(version)
    function_defs=safe_readers()
    for n,(desc,stages) in TOOLS.items():
        function_defs[n]=f'def {n}() -> dict:\n    """{desc}"""\n    return _advance(context, {stages!r})\n'
    for n,func in function_defs.items():
        file=f"tools/{n}/python_function/python_code.py"
        put(file,code+"\n"+func)
        obj("tools",n,{"displayName":n,"pythonFunction":{"name":n,"pythonCode":file}})
    calendar_name="uk_bank_holidays"
    schema_path=f"tools/{calendar_name}/open_api_tool/open_api_schema.yaml"
    fake_path=f"tools/{calendar_name}/tool_fake_config/code_block/python_code.py"
    put(schema_path,advisory_spec())
    put(fake_path,"def fake_tool_call(tool, input, callback_context):\n    if callback_context.variables.get('calendar_unavailable',False):\n        return {}\n    return "+repr(CALENDAR)+"\n")
    obj("tools",calendar_name,{"displayName":calendar_name,"openApiTool":{"name":calendar_name,"openApiSchema":schema_path},
         "toolFakeConfig":{"enableFakeMode":False,"codeBlock":{"pythonCode":fake_path}}})
    for sub,agent in [(False,name),(True,child)]:
        slug=re.sub("[^A-Za-z0-9_]+","_",agent)
        path=f"agents/{slug}/instruction.txt"
        callback=f"agents/{slug}/after_tool_callbacks/handoff.py"
        crisis_hook=f"agents/{slug}/after_agent_callbacks/crisis_handoff.py"
        put(crisis_hook,terminal_callback())
        put(callback,AFTER);put(path,instruction(sub,team,child))
        obj("agents",agent,{"displayName":agent,"instruction":path,"childAgents":[] if sub else [child],
            "tools":(["select_service","lookup_verified_account","read_account_status","statement_service","limit_service",calendar_name] if sub else ["verify_identity"]),
            "afterToolCallbacks":[{"pythonCode":callback,"description":"Log a terminal transfer once, with routing metadata only."}],
            "afterAgentCallbacks":[{"pythonCode":crisis_hook,"description":"Record a human handoff on an exact crisis reply even if an immediate-response guardrail supplied the words."}]})
    for n,k,config,outcome in GUARDS:
        obj("guardrails",n,{"displayName":n,"enabled":True,k:config,"action":{"respondImmediately":{"responses":[{"text":outcome}]}}})
    for c in CASES:
        ev=evaluation(c,child)
        obj("evaluations",ev["displayName"],ev)
    variables=[]
    for k,v in VARS.items():
        typ={str:"STRING",int:"INTEGER",bool:"BOOLEAN",dict:"OBJECT"}[type(v)]
        variables.append({"name":k,"description":k.replace("_"," "),"schema":{"type":typ,"default":v}})
    put("app.json",{"displayName":name,"rootAgent":name,"description":"Fictional bank account services for Capstone 10.",
        "variableDeclarations":variables,"guardrails":[x[0] for x in GUARDS],"toolExecutionMode":"SEQUENTIAL",
        "languageSettings":{"defaultLanguageCode":"en-US"},"timeZoneSettings":{"timeZone":"Asia/Kolkata"},
        "audioProcessingConfig":{"synthesizeSpeechConfigs":{"en-US":{"voice":"en-US-Chirp3-HD-Aoede"}},"bargeInConfig":{"bargeInAwareness":True},"inactivityTimeout":"8s"},
        "loggingSettings":{"redactionConfig":{"enableRedaction":True}}})
    out.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(out,"w",ZIP_DEFLATED) as z:
        for path,val in sorted(resources.items()):
            z.writestr(name+"/"+path,val)
    print(out, len(resources), "files")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--team",help="Actual team number; omit for the unnumbered rehearsal build")
    p.add_argument("--version",choices=("V1","V2"),default="V2")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if a.team and not re.fullmatch(r"\d{1,3}",a.team):
        p.error("team must be a number")
    build(a.team,a.version,a.output)
