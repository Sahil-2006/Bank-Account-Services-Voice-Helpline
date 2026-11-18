const el = id => document.getElementById(id);
const worker = new Worker(new URL("worker.js", import.meta.url), {type:"module"});
const requests = new Map();
let sequence = 0, ready = false, busy = true, closed = false, listening = null;
let cancelListening = null, cancelSpeech = null, voiceCallActive = false;
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
  el("read").disabled = !speech || busy || voiceCallActive;
  el("voice-call").disabled = !ready || !Recognition || !speech || (busy && !voiceCallActive) || (closed && !voiceCallActive);
  el("voice-call").textContent = voiceCallActive ? "End voice call" : "Start voice call";
  el("call-view").disabled = busy || voiceCallActive;
  el("suite-view").disabled = busy || voiceCallActive;
}
function stopListening() {
  if (cancelListening) { const cancel = cancelListening; cancelListening = null; cancel(); }
  else if (listening) { listening.onresult = null; listening.abort(); listening = null; }
}
function stopSpeech() {
  speech?.cancel();
  if (cancelSpeech) { const finish = cancelSpeech; cancelSpeech = null; finish(); }
}
function stopAudio() {
  stopSpeech();
  stopListening();
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
  void speakNow(text);
}
function speakNow(text) {
  if (!speech) return Promise.resolve();
  stopSpeech();
  return new Promise(resolve => {
    let finished = false;
    const done = () => {
      if (finished) return;
      finished = true;
      if (cancelSpeech === done) cancelSpeech = null;
      resolve();
    };
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-IN";
    utterance.onend = done;
    utterance.onerror = done;
    cancelSpeech = done;
    speech.speak(utterance);
  });
}
function listenOnce() {
  return new Promise(resolve => {
    const rec = new Recognition();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    let finished = false;
    const complete = (result, stop = false) => {
      if (finished) return;
      finished = true;
      if (listening === rec) listening = null;
      if (cancelListening === cancel) cancelListening = null;
      rec.onstart = rec.onresult = rec.onerror = rec.onend = null;
      if (stop) { try { rec.stop(); } catch {} }
      if (!voiceCallActive) el("mic").textContent = "Use mic for one reply";
      resolve(result);
    };
    const cancel = () => { complete({cancelled:true}); try { rec.abort(); } catch {} };
    listening = rec;
    cancelListening = cancel;
    rec.onstart = () => { el("audio-status").textContent = "Listening for your reply…"; };
    rec.onresult = event => complete({text:event.results[0][0].transcript || ""}, true);
    rec.onerror = event => complete({error:event.error || "recognition-error"});
    rec.onend = () => complete({error:"no-speech"});
    try { rec.start(); }
    catch { complete({error:"unavailable"}); }
  });
}
async function startVoiceCall() {
  if (voiceCallActive) {
    voiceCallActive = false;
    stopAudio();
    status("Ending voice call…");
    controls();
    return;
  }
  if (busy || !ready || !Recognition || !speech) return;
  busy = true;
  voiceCallActive = true;
  closed = false;
  controls();
  el("audio-status").textContent = "Voice call started. Speak after each prompt.";
  try {
    const first = await request("new");
    show(first, undefined, false);
    let prompt = first.reply;
    let misses = 0;
    while (voiceCallActive && !closed) {
      await speakNow(prompt);
      if (!voiceCallActive || closed) break;
      const result = await listenOnce();
      if (result.cancelled || !voiceCallActive) break;
      if (result.error || !result.text.trim()) {
        if (result.error && !["no-speech","aborted"].includes(result.error)) {
          el("audio-status").textContent = result.error === "not-allowed"
            ? "Microphone access was declined. Allow it in the browser, then start another call."
            : "Speech recognition is unavailable. You can type replies or use the one-reply mic.";
          break;
        }
        misses += 1;
        if (misses >= 2) {
          el("audio-status").textContent = "No reply heard. The call ended; you can type a reply or try voice again.";
          break;
        }
        prompt = "I didn't hear a reply. " + prompt;
        continue;
      }
      misses = 0;
      el("audio-status").textContent = "";
      const turn = await request("turn", result.text);
      show(turn, result.text, false);
      prompt = turn.reply;
      if (closed) await speakNow(prompt);
    }
  } catch (error) {
    if (voiceCallActive) el("audio-status").textContent = "Voice call stopped: " + error.message;
  } finally {
    voiceCallActive = false;
    stopAudio();
    busy = false;
    if (closed) el("audio-status").textContent = "Call ended. Start a new call to speak again.";
    controls();
  }
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
el("read").onchange = () => {if (!el("read").checked) stopSpeech();};
el("voice-call").onclick = startVoiceCall;
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
el("mic").onclick = async () => {
  if (listening) { stopListening(); return; }
  if (busy || !ready || !Recognition) return;
  stopSpeech();
  el("mic").textContent = "Stop listening";
  el("audio-status").textContent = "Listening for your reply…";
  const result = await listenOnce();
  if (result.cancelled) { el("audio-status").textContent = "Listening stopped."; return; }
  if (result.error || !result.text.trim()) {
    el("audio-status").textContent = result.error === "not-allowed"
      ? "Microphone access was declined. You can type a reply."
      : "No speech recognized. Try again or type a reply.";
    return;
  }
  el("audio-status").textContent = "";
  submit(result.text);
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
else if (!speech) el("audio-status").textContent="Speech playback is unavailable in this browser. The one-reply microphone and typed replies may still work.";
try {
  await reset(false);ready = true;status("Ready · V2 Python build");
} catch (err) {status(err.message);}
busy = false;controls();
