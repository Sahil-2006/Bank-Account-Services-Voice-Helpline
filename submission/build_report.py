"""Generate the capstone PDF from recorded local evidence. Run from the project root."""
import json
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib.utils import simpleSplit
from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from pypdf import PdfWriter
from evaluation.catalog import CASES, ROOT, STORIES

OUT=ROOT/"submission"/"Capstone10_Report.pdf"
W,H=A4
c=canvas.Canvas(str(OUT),pagesize=A4)
c.setTitle("Harbour Trust Bank Account Services Voice Helpline")
c.setAuthor("Harbour Trust capstone project")
ink="#102A37"; teal="#006E71"; grey="#52656E"; light="#EAF4F3"; line="#C5D3D5"; white="#FFFFFF"; amber="#834310"
left=42; right=W-left; usable=right-left
def rgb(color):return HexColor(color)
def rect(x,y,w,h,fill,stroke=None):
    c.setFillColor(rgb(fill));c.setStrokeColor(rgb(stroke or fill));c.rect(x,y,w,h,fill=1,stroke=int(stroke is not None))
def txt(x,y,t,size=10,font="Helvetica",color=ink):
    c.setFillColor(rgb(color));c.setFont(font,size);c.drawString(x,y,t)
def para(x,y,w,t,size=10.3,leading=14,color=ink,bold=False):
    st=ParagraphStyle("body",fontName="Helvetica-Bold" if bold else "Helvetica",fontSize=size,leading=leading,textColor=rgb(color))
    p=Paragraph(escape(str(t)),st);_,h=p.wrap(w,900);p.drawOn(c,x,y-h);return y-h
def head(n,title,desc):
    txt(left,H-39,"HARBOUR TRUST   /   ENGINEERING REPORT",8,"Helvetica-Bold",teal)
    c.setFillColor(rgb(grey));c.setFont("Helvetica",8);c.drawRightString(right,H-39,"CAPSTONE 10     •     19 NOVEMBER 2026")
    txt(left,H-86,title,25,"Helvetica-Bold")
    return para(left,H-104,usable,desc,11,15,grey)-20
def footing(i):
    c.setStrokeColor(rgb(line));c.line(left,39,right,39)
    txt(left,24,"BUILDING AI AGENTS FOR DIGITAL CUSTOMER EXPERIENCE SYSTEMS",7.2,"Helvetica",grey)
    c.setFont("Helvetica-Bold",8);c.drawRightString(right,24,str(i)+" / 10");c.showPage()
def sub(y,name):
    txt(left,y-13,name,13,"Helvetica-Bold",teal);return y-24
def table(y,cols,headers,rows,fs=9,lh=12,pad=5):
    def one(y,record,is_header,alt):
        heights=[len(simpleSplit(str(v),"Helvetica-Bold" if is_header else "Helvetica",fs,w-2*pad)) for v,w in zip(record,cols)]
        height=max(heights)*lh+2*pad
        if y-height<45:raise RuntimeError(f"Table overflows: {record[0]} at {y-height}")
        rect(left,y-height,usable,height,teal if is_header else ("#F1F6F6" if alt else white))
        x=left
        for val,w in zip(record,cols):
            for n,t in enumerate(simpleSplit(str(val),"Helvetica-Bold" if is_header else "Helvetica",fs,w-2*pad)):
                txt(x+pad,y-pad-lh+2-n*lh,t,fs,"Helvetica-Bold" if is_header else "Helvetica",white if is_header else ink)
            x+=w
        c.setStrokeColor(rgb(line));c.line(left,y-height,right,y-height)
        return y-height
    y=one(y,headers,True,False)
    for i,row in enumerate(rows):y=one(y,row,False,i%2)
    return y
def note(y,t):return para(left,y,usable,t,9.6,13.4,grey)-12
def link(x,y,label,url):
    txt(x,y,label,9,"Helvetica-Bold",teal)
    c.linkURL(url,(x,y-2,x+c.stringWidth(label,"Helvetica-Bold",9),y+10),relative=0)
def evidence(name):return json.loads((ROOT/"evidence"/name).read_text(encoding="utf-8"))
v1=evidence("local-v1.json");v2=evidence("local-v2.json");audio=evidence("local-audio.json");guards=evidence("local-guardrails.json")
assert v1["cases_sha256"]==v2["cases_sha256"] and len(CASES)==v2["total"]
def compressed(ids):
    groups=[]
    for id_ in ids:
        n=int(id_[1:])
        if groups and groups[-1][0]==id_[0] and groups[-1][2]==n-1:groups[-1][2]=n
        else:groups.append([id_[0],n,n])
    return ", ".join(f"{a}{b:02}" if b==z else f"{a}{b:02}-{a}{z:02}" for a,b,z in groups)
def diagram_node(x,y,w,h,name,body):
    rect(x,y-h,w,h,light,line)
    txt(x+12,y-21,name,12,"Helvetica-Bold")
    para(x+12,y-30,w-24,body,9.1,12,grey)
def arrow(x,y1,y2):
    c.setStrokeColor(rgb(teal));c.setLineWidth(1.6);c.line(x,y1,x,y2)
    c.line(x-4,y2+6,x,y2);c.line(x+4,y2+6,x,y2);c.setLineWidth(0.7)

# 1. Architecture, deliberately one page.
y=head(1,"Bank account services voice helpline","Harbour Trust is a fictional bank. The desk verifies a caller, checks a balance, quotes a statement fee or validates a transfer limit. It routes the result to a simulated service queue.")
y=sub(y,"Application architecture")
diagram_node(left,y,usable,58,"Caller and voice input","Voice or chat enters the root desk. The Studio package selects Aoede for English speech, enables barge-in awareness and configures an eight-second inactivity timeout.")
arrow(W/2,y-58,y-77);y-=79
diagram_node(left,y,usable,64,"Root agent    /    Harbour Trust Voice Desk","Collect customer ID, date of birth and account ending. Read the ID and ending back and wait for confirmation. Verification matches one active fixture. A blocked match or third mismatch routes to a person.")
arrow(W/2,y-64,y-83);y-=85
diagram_node(left,y,usable,75,"Child agent    /    Account Service","Look up the verified account and capture balance, statement or limit. Python tools check status, quote fees, compare limits and resolve channels by date. BankWire moves UK weekends and holidays to the next business day using live GOV.UK data or cache; if both fail, it routes to a person.")
gap=12;half=(usable-gap)/2
x1=left+half/2;x2=left+half+gap+half/2
c.setStrokeColor(rgb(teal));c.line(W/2,y-75,W/2,y-84);c.line(x1,y-84,x2,y-84)
arrow(x1,y-84,y-94);arrow(x2,y-84,y-94);y-=96
diagram_node(left,y,half,69,"Channel transfer","Speak the tool result and terms once. Route with the verified intent and the supported channel.")
diagram_node(left+half+gap,y,half,69,"Human handoff","Keep the best known intent and leave the channel empty. The crisis response interrupts normal service.")
y-=84
y=sub(y,"Controls shared by both agents")
y=para(left,y,usable,"A check on user input screens private numbers and crisis language. Output policy checks account endings, monetary claims and advice. Model safety and prompt security add two provider controls. A callback records destination, reason, intent and channel.",10,14)-13
y=para(left,y,usable,"Session variables carry verified identity, intent, channel, account type, pending quote and handoff. The simulated clock is fixed at 10 November 2026, 09:00 in India. Full account numbers are absent from the dataset.",10,14)-14
y=note(y,f"Completed regression testing: local V2 passed {v2['passed']} of {v2['total']} transcripts. Page 8 shows the actual Studio Build view and the browser balance call; page 9 shows current browser replay results.")
note(y,"Outstanding for submission: the Studio Versions pane, both Studio Evaluate result screenshots, and five human-spoken console calls. The team number and individual contributions also await confirmation.")
footing(1)

# 2. Traceability.
y=head(2,"Requirements and traceability","Each story has acceptance criteria, business rules, error scenarios and linked data in the accompanying workbook. G identifies a golden specification and S identifies a scenario specification.")
matrix=[]
mapping=["Identity matching and lookup","Retry only the failed detail","Intent selection and preservation","Balance response","Status and fail-closed checks","Statement fees and limits","Daily duplicate prevention","Plan transfer caps","Channel/date boundaries and micro-payments","OpenAPI calendar and date adjustment","Human handoff","Scope and advice offer","Crisis input rule and handoff","Private input and safe output","Prompt security and grounded replies"]
for i,story in enumerate(STORIES,1):
    key=f"US-{i:02}";matrix.append((key,story[0],mapping[i-1],compressed([x["id"] for x in CASES if x["story"]==key])))
y=table(y,[47,135,150,usable-332],["Story","Caller need","Tool or guardrail","Linked tests"],matrix,8.8,11.2,5)-18
y=sub(y,"Fictional records")
y=para(left,y,usable,"Nine fictional records cover Basic and Premium plans, blocked, frozen, dormant and missing statuses, a missing linked account, a zero balance and two prior-statement dates. The desk uses the authenticated session identity for each lookup.",10,14)-10
note(y,"For a reproducible balance call, enter HT4102, give 14 June 1993 and ending 0042, confirm, then choose balance. The expected result is 18,420 rupees and an Instant Pay handoff.")
footing(2)

# 3 and 4. Full test list, paired columns.
def suite_grid(y,kind):
    cases=[x for x in CASES if x["kind"]==kind];half=(len(cases)+1)//2;w=(usable-14)/2
    for col,items in enumerate((cases[:half],cases[half:])):
        off=left+col*(w+14);pos=y
        rect(off,pos-20,w,20,teal);txt(off+6,pos-14,"CASE",8,"Helvetica-Bold",white);txt(off+40,pos-14,"TEST",8,"Helvetica-Bold",white);pos-=20
        for i,row in enumerate(items):
            lines=simpleSplit(row["title"],"Helvetica",8.8,w-46);h=max(21,8+10*len(lines))
            rect(off,pos-h,w,h,white if i%2==0 else "#F0F5F5")
            txt(off+6,pos-14,row["id"],8.6,"Helvetica-Bold",teal)
            for j,t in enumerate(lines):txt(off+40,pos-14-j*10,t,8.8)
            pos-=h
        if col==0:end=pos
        else:end=min(end,pos)
    return end-19
y=head(3,"Golden regression tests","The 29 golden specifications define caller turns and expected replies. Studio definitions also carry tool, internal agent transfer or session-variable expectations where applicable.")
y=suite_grid(y,"golden")
y=sub(y,"Thresholds and dates")
y=table(y,[145,usable-145],["Boundary","Expected decision"],[
 ("3, 12 and 36 months","Digital fees are 0, 100 and 300 rupees. Printed fees are 100, 250 and 500."),
 ("Fractional months","3.01 months enters the second tier. 12.01 enters the third. 36.01 routes to a person."),
 ("25,000 and 1,00,000 rupees","Basic and Premium accept their exact daily caps. One rupee above either cap routes to a person."),
 ("31 Dec 2026 / 1 Jan 2027","PassBook Express stops at the year boundary. BankWire becomes BankWire Plus."),
 ("Holiday and micro-payment","KitePay accepts 1 rupee only. A UK weekend or holiday moves to the next business day.")],9,12,5)
footing(3)
y=head(4,"Scenario tests and regression results","The 27 scenario specifications contain a caller goal and scoring rubrics for Studio. The local runner replays fixed transcripts. It does not simulate a generative caller.")
y=suite_grid(y,"scenario")
y=sub(y,"Unchanged suite across two builds")
y=table(y,[141,81,80,usable-302],["Execution","V1","V2","Evidence"],[
 ("Golden replay","27 / 29","29 / 29","V1 misses KitePay and calendar boundary"),
 ("Scenario replay","19 / 27","27 / 27","Ten baseline misses overall"),
 ("All local transcripts","46 / 56","56 / 56","82.1% to 100.0%"),
 ("Hosted Evaluate","Pending","Pending","Google Cloud billing required")],9,11,4)-14
y=para(left,y,usable,"V1 misses: G23 and G29; S03, S04, S09, S11, S14, S15, S18 and S23. These cover the 1-rupee KitePay route, holiday-date adjustment, unknown-ID handoff, third verification mismatch, frozen statements, crisis phrasing, calendar fallback and outage, harmful wording, and failed-field-only retry. V2 closes all ten locally.",9.8,13.2)
footing(4)

# 5. Safety.
y=head(5,"Guardrail evidence","Five Studio guardrails cover four provider types. Fifteen local probes exercised the input classifiers and output validator. Each row below includes a trigger, a harmless control and a reworded case.")
items=[
 ("Private identifiers","Regex blocklist on user input","Refuse without repeating the number. Four repeated digit groups and a card spoken as words triggered the local filter. A spoken four-digit ending continued."),
 ("Crisis support","Rules policy on user input in both agents","Say the exact approved response. The local desk logged a human handoff for a direct disclosure and a paraphrase. Tiredness plus a statement request continued."),
 ("Grounded account replies","Rules policy on agent output","Replace unsupported money, advice or a full account number with the safe reply. An invented 999-rupee fee and an eight-digit account disclosure were replaced. A supported 100-rupee fee passed."),
 ("Harm safety","Model safety on input and output","Use the medium dangerous-content threshold to screen harmful requests while allowing ordinary banking calls. Two harm phrasings activated the local counterpart. A balance request continued."),
 ("Prompt security","Default prompt guard on input","Use the provider default policy with fail-closed behavior. Two instruction-override phrasings activated the local counterpart. Asking about a transfer limit continued.")]
y=table(y,[106,116,usable-222],["Guardrail","Type and scope","Outcome and observed local behavior"],items,9.15,12.2,6)-19
y=sub(y,"Voice privacy and layered crisis handling")
y=para(left,y,usable,"A raw digit pattern cannot match a card spoken entirely as words. The local guard normalizes digit words for detection and preserves a legitimate four-digit ending. In the audio probe, unconstrained recognition rendered four spoken digits as 4532. The service vocabulary returned the words.",10,14)-12
y=para(left,y,usable,"Both agent instructions and the native crisis guardrail use the same response string. G24 and G25 exercise entry and mid-statement cases. S11 exercises a paraphrase. Studio must still confirm that a native immediate response and its terminal handoff both fire on the same turn.",10,14)-11
note(y,"All 15 local catch, control and paraphrase checks passed. The local pattern matcher covers the tested wording. The behavior of the provider's model safety and prompt guard still needs a hosted run.")
footing(5)

# 6. Actual acoustic results.
y=head(6,"Voice and acoustic evidence","Microsoft Zira generated fictional caller audio. Windows Speech Recognizer transcribed the PCM and the local desk consumed its text. These five probes provide acoustic evidence ahead of the required human-spoken Studio calls.")
spoken=[
 ("Clean balance call","ID, DOB, 0042, yes, balance","Digit words retained. DOB became June 14, 1993. Heard yes and balance.","Pass. Instant Pay received the balance tag."),
 ("Noisy ID and retry","ID in seeded noise, then clean repeat","No transcript for noisy ID. Clean repeat matched the identity sequence.","Pass. Gentle prompt and eventual transfer."),
 ("Interrupt an agent prompt","Representative, 400 ms into a prompt","No usable transcript from the overlapped recording.","Fail. Handoff did not fire."),
 ("Zero mid-step","Statement, then zero","Heard statement and zero while waiting for months.","Pass. Human handoff with statement intent."),
 ("Crisis at entry","I do not want to live anymore","Heard the whole phrase without a change.","Pass. Exact script and human handoff.")]
y=table(y,[92,119,146,usable-357],["Probe","Caller audio","Recognized transcript","Local outcome"],spoken,9.2,12.4,5)-18
y=sub(y,"Three differences from typed chat")
for t in [
 "A typed representative request routed immediately. Unconstrained speech produced “Brett presented if”. Adding a service vocabulary recovered “representative” in isolation. Overlap still failed.",
 "A typed “no” corrected the readback. Free dictation rendered the word “now”. A command grammar recovered “no”, so a caller can reject a confirmation. Single-word menu digits still sometimes yield silence.",
 "A typed ISO date parsed directly. Spoken DOB arrived as “June 14, 1993”. The date parser accepts month names and spoken ordinals. The recognized DOB now verifies with the same fixture."]:
    y=para(left,y,usable,t,10.1,14.2)-10
y=sub(y,"Remaining console checks")
note(y,"Run these five calls with a human speaker in Studio audio mode. Record the actual transcripts, whether playback stopped during barge-in, and the Versions and Evaluate screens. Windows audio-file recognition cannot measure a live headset's interruption latency.")
footing(6)

# 7. Evidence lineage.
y=head(7,"Release state and limitations","The completed browser desk, local implementation, Studio packages and workbook are available for review. A billing-enabled course project is required to produce the console records specified in the assignment.")
y=sub(y,"What can be reproduced")
y=table(y,[160,usable-160],["Artifact","Evidence and scope"],[
 ("Local builds","The local-v1 Git tag preserves the baseline. evidence/local-v1.json and local-v2.json carry identical test-specification hashes and each case outcome."),
 ("Studio packages","Separate V1 and V2 archives contain two agents, instructions, Python tools, five guardrails and 56 evaluation definitions. RosterPending identifies a build made before the team number was supplied."),
 ("Audio and guardrails","evidence/local-audio.json contains every synthetic turn, ASR transcript and reply. evidence/local-guardrails.json records observed trigger and control results."),
 ("Business data","Fixtures contain invented customers and account endings. Local SQLite prevents a second statement reservation across calls. Studio uses a seeded already-sent date and simulated queues."),
 ("External advisory","The Vercel API validates live GOV.UK data and has a bundled cache. BankWire uses England and Wales for the fictional UK clearing leg. India branch opening hours are outside this feed.")],9.5,13,6)-17
y=sub(y,"Hosted evidence still outstanding")
y=para(left,y,usable,"The available billing notice says trial activation requires prepayment. Although the native Builder screenshot confirms the `harbour-trust-voice-helpline` project in region `us`, the billing link and hosted write access are unverified. No detailed Studio result pane, hosted pass rate, managed V1/V2 record or five live spoken call outcomes were captured.",10.3,14.6)-12
y=para(left,y,usable,"When the course project can write in Studio, save and evaluate V1 and V2 in the same application. Capture the full-screen Versions pane and both run results. Record five spoken calls, reconcile any new failures and add the confirmed team number and actual contributions before submission.",10.3,14.6)-14
y=sub(y,"Implementation references")
link(left,y-7,"Google Cloud   /   Studio import format","https://docs.cloud.google.com/gemini-enterprise-cx/cx-agent-studio/reference/export")
link(left,y-23,"Google Cloud   /   Evaluations","https://docs.cloud.google.com/gemini-enterprise-cx/cx-agent-studio/evaluation")
link(left,y-39,"GOV.UK   /   Bank holiday calendar","https://www.gov.uk/bank-holidays")
footing(7)

def screenshot_page(number, title, intro, file, caption, detail):
    y=head(number,title,intro)
    img=ImageReader(str(ROOT/"evidence"/"browser"/file))
    iw,ih=img.getSize()
    scale=min(usable/iw,452/ih)
    w,h=iw*scale,ih*scale
    x=(W-w)/2
    c.drawImage(img,x,y-h,w,h)
    c.setStrokeColor(rgb(line));c.rect(x,y-h,w,h,fill=0,stroke=1)
    y=y-h-15
    y=para(left,y,usable,caption,10,14,bold=True)-10
    y=para(left,y,usable,detail,10,14)-12
    link(left,y,"Open the original screenshot","https://github.com/Sahil-2006/Bank-Account-Services-Voice-Helpline/blob/main/evidence/browser/"+file)
    link(left,y-17,"Open the live browser demonstration","https://harbour-trust-voice-capstone-10.vercel.app/")
    footing(number)

def build_and_balance_page():
    y=head(8,"Studio build and browser balance call","The Studio image is a genuine capture of the configured Build canvas. The browser image shows a completed fictional balance call; neither image represents a Studio Evaluate score.")
    studio=ImageReader(str(ROOT/"evidence"/"studio"/"build-agent-flow.png"))
    iw,ih=studio.getSize();scale=min(usable/iw,270/ih);w,h=iw*scale,ih*scale
    x=(W-w)/2;c.drawImage(studio,x,y-h,w,h)
    c.setStrokeColor(rgb(line));c.rect(x,y-h,w,h,fill=0,stroke=1)
    y=para(left,y-h-10,usable,"Figure 1. Native CX Agent Studio Build view with two agents, tools, guardrails and callbacks.",9.5,12,bold=True)-16
    gap=16;col=(usable-gap)/2;balance=ImageReader(str(ROOT/"evidence"/"browser"/"balance-handoff-panel.jpg"))
    iw,ih=balance.getSize();scale=min(col/iw,146/ih);w,h=iw*scale,ih*scale
    c.drawImage(balance,left,y-146+(146-h)/2,w,h)
    c.setStrokeColor(rgb(line));c.rect(left,y-146,col,146,fill=0,stroke=1)
    x=left+col+gap
    text_y=para(x,y-4,col,"Figure 2. Browser V2 demo",10.1,13,teal,bold=True)-6
    text_y=para(x,text_y,col,"The demo returned 18,420 rupees for fictional caller HT4102 and recorded an Instant Pay handoff.",9.7,13)-7
    text_y=para(x,text_y,col,"The Studio notification reports a scheduled run completed, but no detailed result pane was available. No hosted pass rate is claimed.",9.7,13)-8
    y=min(y-153,text_y)-10
    y=para(left,y,usable,"The browser call used typed replies. The account and identity values are fictional.",9.4,12)-6
    link(left,y,"Open the original Studio screenshot","https://github.com/Sahil-2006/Bank-Account-Services-Voice-Helpline/blob/main/evidence/studio/build-agent-flow.png")
    link(left,y-17,"Open the live browser demonstration","https://harbour-trust-voice-capstone-10.vercel.app/")
    footing(8)

build_and_balance_page()
screenshot_page(9,"Observed regression pass rates",
    "Both packaged builds ran against 56 fixed transcripts in the public browser demo. This production screenshot records local browser replay after completion and agrees with the independent Python replay.",
    "regression-results.jpg","Figure 3. V1 passed 46 of 56 cases (82.1%). V2 passed 56 of 56 (100.0%).",
    "The V1 baseline missed G23 and G29 plus scenarios S03, S04, S09, S11, S14, S15, S18 and S23. V2 passed them all. These are deterministic local replay rates. Google-hosted Evaluate rates have not been measured.")

def studio_illustration(slug,title,columns,records):
    width,height=usable,133
    graphic=Drawing(width,height)
    def box(x,y,w,h,color):
        graphic.add(Rect(x,y,w,h,fillColor=rgb(color),strokeColor=None))
    def label(x,y,value,size=10,font="Helvetica",color=ink):
        graphic.add(String(x,y,value,fontName=font,fontSize=size,fillColor=rgb(color)))
    box(0,0,width,height,"#F0F5F3")
    box(0,height-28,width,28,"#174A49")
    label(12,height-18,"STUDIO EVIDENCE GUIDE",8,"Helvetica-Bold",white)
    label(width-169,height-18,"ILLUSTRATION  /  NO HOSTED RUN",8,"Helvetica-Bold",white)
    label(12,height-49,title,14,"Helvetica-Bold")
    widths=[0,169,342]
    for i,t in enumerate(columns):label(12+widths[i],height-67,t,8.3,"Helvetica-Bold",teal)
    for j,record in enumerate(records):
        for i,t in enumerate(record):label(12+widths[i],height-86-j*17,t,9.4)
    box(0,0,width,17,"#E0EAE5")
    label(12,5,"A real console capture is still required for this view.",8,"Helvetica",grey)
    folder=ROOT/"evidence"/"studio-illustrations"
    folder.mkdir(parents=True,exist_ok=True)
    renderSVG.drawToFile(graphic,str(folder/(slug+".svg")))
    return graphic

y=head(10,"Studio evidence capture guide","The following three illustrations identify the fields needed from the team's own console. They use the assignment's naming pattern. No managed version ID or hosted pass rate has been recorded.")
specs=[
    ("versions","Versions",["Version label","Application","Native record"],
     [["Team<NN>-V1","Harbour Trust Voice Desk","Awaiting capture"],["Team<NN>-V2","Harbour Trust Voice Desk","Awaiting capture"]]),
    ("evaluate-v1","Evaluate results for V1",["Version","Passed / executed","Studio pass rate"],
     [["Team<NN>-V1","Pending hosted run","Unmeasured"]]),
    ("evaluate-v2","Evaluate results for V2",["Version","Passed / executed","Studio pass rate"],
     [["Team<NN>-V2","Pending hosted run","Unmeasured"]])]
for spec in specs:
    graphic=studio_illustration(*spec)
    renderPDF.draw(graphic,c,left,y-graphic.height)
    y-=graphic.height+16
y=sub(y,"Evidence required by the assignment")
note(y,"Section 10 requires full-screen captures with the team's agent names visible. Use the actual Versions pane and both completed Evaluate result screens. Section 7 also requires five spoken calls in the team's own console.")
footing(10)
c.save()
writer=PdfWriter(clone_from=BytesIO(OUT.read_bytes()))
for image_path in sorted((ROOT/"evidence"/"browser").glob("*.jpg")):
    writer.add_attachment(image_path.name,image_path.read_bytes())
with OUT.open("wb") as target:
    writer.write(target)
print(OUT)
