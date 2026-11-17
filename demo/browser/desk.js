const el = id => document.getElementById(id);
const worker = new Worker(new URL("worker.js", import.meta.url), {type:"module"});
const requests = new Map();
let sequence = 0, ready = false, busy = true, closed = false, listening = null;
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const speech = window.speechSynthesis;
const status = text => { el("status").textContent = text; };

function request(action, text = "") {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    requests.set(id, {resolve,reject});
    worker.postMessage({id,action,text});
  });
}
worker.onmessage = ({data}) => {
  const pending = requests.get(data.id);
  if (!pending) return;
  requests.delete(data.id);
  if (data.error) pending.reject(new Error(data.error));
  else pending.resolve(data.value);
};
worker.onerror = () => {
  ready = false; controls();
  const message = "The helpline could not load. Refresh to try again.";
  status(message);
  for (const pending of requests.values()) pending.reject(new Error(message));
  requests.clear();
};
function controls() {
  for (const id of ["reply","send","mic"]) el(id).disabled = !ready || busy || closed;
  el("mic").disabled ||= !Recognition;
  for (const id of ["example","reset","run"]) el(id).disabled = !ready || busy;
  el("read").disabled = !speech;
}
function stopAudio() {
  speech?.cancel();
  if (listening) { listening.onresult = null; listening.abort(); listening = null; }
}
function message(who, text) {
  const item = document.createElement("div");
  item.className = "utterance" + (who === "Caller" ? " caller" : "");
  const label = document.createElement("strong"), body = document.createElement("p");
  label.textContent = who; body.textContent = text;
  item.append(label,body); el("log").append(item); el("log").scrollTop = el("log").scrollHeight;
}
function speak(text) {
  if (!el("read").checked || !speech) return;
  speech.cancel();
  const u = new SpeechSynthesisUtterance(text); u.lang="en-IN"; speech.speak(u);
}
function show(result, caller, read = true) {
  if (caller !== undefined) message("Caller", result.private ? "[Private digits withheld]" : caller);
  message("Voice desk",result.reply);
  if (read) speak(result.reply);
  const route = result.handoff;
  closed = result.stage === "closed";
  el("handoff").hidden = !closed;
  if (closed) {
    const dest = route.destination === "human" ? "Human representative" : route.channel;
    el("handoff").textContent = "Handoff recorded · " + dest + (route.intent ? " · "+route.intent : "");
  }
}
async function reset(read = true) {
  stopAudio(); el("log").replaceChildren(); el("reply").value = "";
  show(await request("new"), undefined, read);
}
async function task(callback) {
  if (busy || !ready) return;
  busy = true; controls();
  try { await callback(); }
  catch (err) {status(err.message);}
  finally {busy = false;controls();}
}
function view(call) {
  stopAudio();
  el("call-panel").hidden = !call; el("suite-panel").hidden = call;
  el("call-view").setAttribute("aria-pressed",String(call));
  el("suite-view").setAttribute("aria-pressed",String(!call));
}
el("call-view").onclick = () => view(true);
el("suite-view").onclick = () => view(false);
el("reset").onclick = () => task(() => reset());
el("read").onchange = () => {if (!el("read").checked) speech?.cancel();};
async function submit(text) {
  await task(async () => {
    if (closed || !text.trim()) return;
    stopAudio(); el("reply").value = "";
    show(await request("turn",text),text);
  });
  if (!closed) el("reply").focus();
}
el("reply-form").onsubmit = event => {event.preventDefault();submit(el("reply").value);};
el("example").onclick = () => task(async () => {
  await reset(false);
  for (const value of ["HT4102","14 June 1993","0042","yes","balance"]) {
    show(await request("turn",value),value,value === "balance");
  }
});
el("mic").onclick = () => {
  if (listening) {listening.stop();return;}
  speech?.cancel();
  const rec = new Recognition(); rec.lang = "en-IN"; rec.interimResults = false;
  let heard = false;
  rec.onstart = () => {el("mic").textContent = "Stop listening";el("audio-status").textContent = "Listening for your reply…";};
  rec.onerror = e => {el("audio-status").textContent = e.error==="not-allowed" ? "Microphone access was declined. You can type a reply." : "Speech recognition is unavailable. You can type a reply.";};
  rec.onend = () => {if(listening===rec) listening=null;el("mic").textContent="Use microphone";if (!heard && el("audio-status").textContent==="Listening for your reply…") el("audio-status").textContent="No speech recognized. Try again or type a reply.";};
  rec.onresult = e => {heard=true;const text=e.results[0][0].transcript;el("audio-status").textContent="";listening=null;submit(text);};
  try {listening=rec;rec.start();} catch {listening=null;el("audio-status").textContent="Microphone unavailable. You can type a reply.";}
};
function node(tag,text,className) {
  const n=document.createElement(tag);n.textContent=text;if(className)n.className=className;return n;
}
el("run").onclick = () => task(async () => {
  stopAudio();el("results").replaceChildren(node("p","Running both Python builds…"));
  const runs=await request("suite"), cards=node("div","","cards");
  const list=node("div","");
  for (const result of runs) {
    const box=node("section","","metric");
    box.append(node("p",result.version+" · "+(result.version==="V1"?"baseline":"revised")),node("strong",result.passed+" / "+result.total),
      node("p",((100*result.passed/result.total).toFixed(1))+"% passed"));
    cards.append(box);
    for (const failure of result.failed) {
      const row=node("div","","case");
      row.append(node("b",result.version+" · "+failure.id+"   "),document.createTextNode(failure.title),
        node("p","Observed reply: "+failure.actual,"details"));list.append(row);
    }
  }
  el("results").replaceChildren(cards,node("h3","Failed cases"),list);
});
if (!Recognition) el("audio-status").textContent="Speech recognition is unavailable in this browser. Typed replies work.";
try {
  await reset(false);ready = true;status("Ready · V2 Python build");
} catch (err) {status(err.message);}
busy = false;controls();
