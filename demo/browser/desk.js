const el = id => document.getElementById(id);
const worker = new Worker(new URL("worker.js", import.meta.url), {type:"module"});
const requests = new Map();
let sequence = 0, ready = false, busy = true, closed = false, listening = null;
let cancelListening = null, cancelSpeech = null, voiceCallActive = false;
let fishVoiceAvailable = false, qwenAsrAvailable = false, qwenReplyAvailable = false, fishAudio = null, fishAudioUrl = null, speechController = null;
let cancelRecording = null;
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
  if (data.type === "progress") { status(data.message); return; }
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
  const voiceOutputAvailable = Boolean(speech || fishVoiceAvailable);
  const voiceInputAvailable = Boolean(Recognition || (qwenAsrAvailable && window.MediaRecorder && navigator.mediaDevices?.getUserMedia));
  for (const id of ["reply","send","mic"]) el(id).disabled = !ready || busy || closed;
  el("mic").disabled ||= !voiceInputAvailable;
  for (const id of ["example","reset","run"]) el(id).disabled = !ready || busy;
  el("read").disabled = !voiceOutputAvailable || busy || voiceCallActive;
  el("voice-call").disabled = !ready || !voiceInputAvailable || !voiceOutputAvailable || (busy && !voiceCallActive) || (closed && !voiceCallActive);
  el("voice-call").textContent = voiceCallActive ? "End voice call" : "Start voice call";
  el("call-view").disabled = busy || voiceCallActive;
  el("suite-view").disabled = busy || voiceCallActive;
}
function stopListening() {
  if (cancelRecording) { const cancel = cancelRecording; cancelRecording = null; cancel(); }
  if (cancelListening) { const cancel = cancelListening; cancelListening = null; cancel(); }
  else if (listening) { listening.onresult = null; listening.abort(); listening = null; }
}
function stopSpeech() {
  speech?.cancel();
  if (speechController) { const controller = speechController; speechController = null; controller.abort(); }
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
  if (!el("read").checked || (!speech && !fishVoiceAvailable)) return;
  void speakNow(text);
}
function speakBrowser(text) {
  if (!speech) return Promise.resolve();
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
function playFishAudio(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    let finished = false;
    const finish = error => {
      if (finished) return;
      finished = true;
      if (fishAudio === audio) fishAudio = null;
      if (fishAudioUrl === url) fishAudioUrl = null;
      audio.onended = audio.onerror = null;
      audio.pause();
      audio.removeAttribute("src");
      URL.revokeObjectURL(url);
      if (cancelSpeech === cancel) cancelSpeech = null;
      if (error) reject(error);
      else resolve();
    };
    const cancel = () => finish();
    fishAudio = audio;
    fishAudioUrl = url;
    cancelSpeech = cancel;
    audio.onended = () => finish();
    audio.onerror = () => finish(new Error("Fish Audio playback failed"));
    audio.play().catch(finish);
  });
}
async function speakNow(text) {
  stopSpeech();
  if (fishVoiceAvailable) {
    const controller = new AbortController();
    speechController = controller;
    try {
      const response = await fetch("/api/voice/tts", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({text}), signal:controller.signal
      });
      if (!response.ok) throw new Error("Fish Audio request failed");
      const audio = await response.blob();
      if (controller.signal.aborted) return;
      if (speechController === controller) speechController = null;
      await playFishAudio(audio);
      return;
    } catch (error) {
      if (controller.signal.aborted) return;
      fishVoiceAvailable = false;
      controls();
      el("audio-status").textContent = "Fish Audio is unavailable; using the browser voice instead.";
    } finally {
      if (speechController === controller) speechController = null;
    }
  }
  await speakBrowser(text);
}
function listenOnce(language = "en-IN") {
  return new Promise(resolve => {
    const rec = new Recognition();
    rec.lang = language;
    rec.interimResults = true;
    rec.maxAlternatives = 3;
    let finished = false;
    let partial = "";
    let timeout;
    const complete = (result, stop = false) => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      if (listening === rec) listening = null;
      if (cancelListening === cancel) cancelListening = null;
      rec.onstart = rec.onresult = rec.onerror = rec.onend = null;
      rec.onaudiostart = rec.onspeechstart = rec.onspeechend = null;
      if (stop) { try { rec.stop(); } catch {} }
      if (!voiceCallActive) el("mic").textContent = "Use mic for one reply";
      resolve(result);
    };
    const cancel = () => { complete({cancelled:true}); try { rec.abort(); } catch {} };
    listening = rec;
    cancelListening = cancel;
    rec.onstart = () => { el("audio-status").textContent = "Microphone active. Speak now…"; };
    rec.onaudiostart = () => { el("audio-status").textContent = "Listening… say one short reply."; };
    rec.onspeechstart = () => { el("audio-status").textContent = "Speech detected…"; };
    rec.onspeechend = () => { el("audio-status").textContent = "Got your speech. Processing…"; };
    rec.onresult = event => {
      const finalParts = [], interimParts = [];
      for (let i=0;i<event.results.length;i++) {
        const result = event.results[i];
        const text = result[0]?.transcript?.trim();
        if (!text) continue;
        (result.isFinal ? finalParts : interimParts).push(text);
      }
      if (finalParts.length) {
        complete({text:finalParts.join(" ")}, true);
      } else if (interimParts.length) {
        partial = interimParts.join(" ");
        el("audio-status").textContent = "I hear: “" + partial + "”";
      }
    };
    rec.onerror = event => complete({error:event.error || "recognition-error"});
    rec.onend = () => complete(partial ? {text:partial} : {error:"no-speech"});
    timeout = setTimeout(() => complete(partial ? {text:partial} : {error:"no-speech"}, true),15_000);
    try { rec.start(); }
    catch (error) { complete({error:error?.name === "NotAllowedError" ? "not-allowed" : "unavailable"}); }
  });
}
async function listenForReply() {
  let result = await listenOnce("en-IN");
  if (result.error === "language-not-supported") {
    el("audio-status").textContent = "English (India) is unavailable here. Trying English (US)…";
    result = await listenOnce("en-US");
  }
  return result;
}
function chooseRecordingType() {
  if (!window.MediaRecorder) return "";
  return ["audio/webm;codecs=opus","audio/webm","audio/mp4","audio/ogg;codecs=opus","audio/ogg"]
    .find(type => !MediaRecorder.isTypeSupported || MediaRecorder.isTypeSupported(type)) || "";
}
async function transcribeClip(blob, durationMs) {
  const audio = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("The microphone recording could not be read."));
    reader.onload = () => resolve(String(reader.result || ""));
    reader.readAsDataURL(blob);
  });
  const response = await fetch("/api/voice/asr", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify({audio,mimeType:blob.type,durationMs})
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || "Qwen transcription is unavailable.");
  return {text:typeof result.text === "string" ? result.text.trim() : ""};
}
async function requestTurn(text) {
  const result = await request("turn",text);
  if (!result.unrecognized || result.private || !qwenReplyAvailable || /\b(?:\d{4,}|\d{3}[- ]\d{3}[- ]\d{4}|\S+@\S+\.\S+)\b/.test(text)) return result;
  el("audio-status").textContent = "Checking this unrecognized question with Qwen…";
  try {
    const response = await fetch("/api/voice/qwen", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({question:String(text).slice(0,600)})
    });
    const generated = await response.json().catch(() => ({}));
    const answer = typeof generated.text === "string" ? generated.text.trim() : "";
    const unsafe = /(?:₹|\b(?:rupees|inr|rs\.?))\s*\d|\b\d[\d,]*\s+rupees\b|\b(?:balance|fee|limit)\s+(?:is|of)\s+\d|\b(?:pin|password|otp|aadhaar|card number)\b/i.test(answer);
    if (response.ok && answer && answer.length <= 450 && !unsafe) {
      result.reply = answer + " " + "Would you like your balance, a statement, or a transfer limit?";
      el("audio-status").textContent = "Qwen handled an unrecognized question; regular services still use scripted rules.";
    } else {
      el("audio-status").textContent = "Qwen could not verify an answer; the scripted service menu is shown.";
    }
  } catch { el("audio-status").textContent = "Qwen is unavailable; the scripted service menu is shown."; }
  return result;
}
function recordQwenReply(stream) {
  return new Promise(resolve => {
    const type = chooseRecordingType();
    if (!type || !stream?.getAudioTracks?.().some(track => track.readyState === "live")) {
      resolve({error:"recorder-unavailable"}); return;
    }
    let recorder, audioContext, analyser, timer, stopRequested = false, settled = false, stopReason = null;
    let chunks = [], speechDetected = false, noiseFloor = 0.003, baselineSamples = 0;
    let speechRun = 0, quietSince = 0;
    const began = Date.now();
    const finish = reason => {
      if (stopRequested || settled) return;
      stopRequested = true;
      stopReason = reason;
      clearInterval(timer);
      clearTimeout(timer);
      try { if (recorder?.state !== "inactive") recorder.stop(); }
      catch { settled = true; resolve(reason || {error:"recording-failed"}); }
    };
    cancelRecording = () => finish({cancelled:true});
    try {
      recorder = new MediaRecorder(stream, {mimeType:type});
      if (window.AudioContext || window.webkitAudioContext) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        audioContext = new AudioCtx();
        const source = audioContext.createMediaStreamSource(stream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        source.connect(analyser);
      }
      recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
      recorder.onerror = () => finish({error:"recording-failed"});
      recorder.onstop = async () => {
        clearInterval(timer);
        clearTimeout(timer);
        if (cancelRecording) cancelRecording = null;
        try { await audioContext?.close(); } catch {}
        if (stopReason?.cancelled || stopReason?.error) { settled = true; resolve(stopReason); return; }
        if (!speechDetected) { settled = true; resolve({error:"no-speech"}); return; }
        const blob = new Blob(chunks, {type:recorder.mimeType || type});
        if (!blob.size) { settled = true; resolve({error:"empty-audio"}); return; }
        const durationMs = Math.min(Date.now() - began,15_000);
        el("audio-status").textContent = "Transcribing this short microphone clip with Qwen…";
        try { settled = true; resolve(await transcribeClip(blob,durationMs)); }
        catch (error) { settled = true; resolve({error:"qwen-asr-error", detail:providerError(error)}); }
      };
      recorder.start(150);
      el("audio-status").textContent = "Qwen STT is listening. Speak your reply now…";
      if (!analyser) {
        timer = setTimeout(() => finish({error:"audio-meter-unavailable"}), 100);
        return;
      }
      const frame = new Float32Array(analyser.fftSize);
      timer = setInterval(() => {
        const elapsed = Date.now() - began;
        if (elapsed >= 15_000) { finish({}); return; }
        analyser.getFloatTimeDomainData(frame);
        let energy = 0;
        for (const sample of frame) energy += sample * sample;
        const level = Math.sqrt(energy / frame.length);
        if (elapsed < 350 && !speechDetected) {
          noiseFloor = (noiseFloor * baselineSamples + level) / (baselineSamples + 1);
          baselineSamples++;
        }
        const threshold = Math.max(0.009, noiseFloor * 2.15);
        if (level >= threshold) {
          speechRun++;
          quietSince = 0;
          if (speechRun >= 2) speechDetected = true;
        } else {
          speechRun = 0;
          if (speechDetected && !quietSince) quietSince = Date.now();
          if (speechDetected && Date.now() - quietSince >= 950) { finish({}); return; }
        }
        if (!speechDetected && elapsed >= 8_000) finish({error:"no-speech"});
      }, 100);
    } catch {
      clearInterval(timer);
      clearTimeout(timer);
      try { audioContext?.close(); } catch {}
      if (cancelRecording) cancelRecording = null;
      settled = true;
      resolve({error:"recorder-unavailable"});
    }
  });
}
async function listenForReplyWithQwen(stream) {
  if (qwenAsrAvailable && stream && window.MediaRecorder) {
    const result = await recordQwenReply(stream);
    if (result.cancelled || result.text || result.error === "no-speech") return result;
    if (!Recognition) return result;
    el("audio-status").textContent = (result.detail || "Qwen STT is unavailable.") + " Trying browser speech recognition…";
  }
  return listenForReply();
}
function recognitionError(error) {
  if (error === "not-allowed" || error === "service-not-allowed") {
    return "Microphone access is blocked. Allow it in the browser's site permissions, reload, and try again.";
  }
  if (error === "audio-capture") return "No microphone was found. Connect one or use typed replies.";
  if (error === "network") return "Browser speech recognition could not reach its speech service. Check the connection or type your reply.";
  if (error === "language-not-supported") return "This browser does not support English (India) recognition. Use typed replies or another supported browser.";
  return "Speech recognition is unavailable. You can type replies or use the one-reply mic.";
}
function providerError(error) {
  return String(error?.message || error?.msg || error?.error || error || "The speech service is unavailable.");
}
async function startVoiceCall() {
  if (voiceCallActive) {
    voiceCallActive = false;
    stopAudio();
    status("Ending voice call…");
    controls();
    return;
  }
  const canUseQwenAsr = qwenAsrAvailable && window.MediaRecorder && navigator.mediaDevices?.getUserMedia;
  if (busy || !ready || (!Recognition && !canUseQwenAsr) || (!speech && !fishVoiceAvailable)) return;
  busy = true;
  voiceCallActive = true;
  closed = false;
  controls();
  el("audio-status").textContent = "Voice call started. Speak after each prompt.";
  let microphone;
  try {
    if (canUseQwenAsr) {
      try { microphone = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}}); }
      catch { el("audio-status").textContent = Recognition ? "Qwen mic capture is unavailable; using browser speech recognition." : "Allow microphone access, connect a microphone, and try again."; }
    }
    if (!voiceCallActive) return;
    const first = await request("new");
    show(first, undefined, false);
    let prompt = first.reply;
    let misses = 0;
    while (voiceCallActive && !closed) {
      await speakNow(prompt);
      if (!voiceCallActive || closed) break;
      const result = await listenForReplyWithQwen(microphone);
      if (result.cancelled || !voiceCallActive) break;
      if (result.error || !result.text.trim()) {
        if (result.error && !["no-speech","aborted"].includes(result.error)) {
          el("audio-status").textContent = result.detail || recognitionError(result.error);
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
      const turn = await requestTurn(result.text);
      show(turn, result.text, false);
      prompt = turn.reply;
      if (closed) await speakNow(prompt);
    }
  } catch (error) {
    const detail = providerError(error);
    if (voiceCallActive) el("audio-status").textContent = "Voice call stopped: " + detail;
  } finally {
    if (microphone) microphone.getTracks().forEach(track => track.stop());
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
    show(await requestTurn(text),text);
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
  if (listening || cancelRecording) { stopListening(); return; }
  const canUseQwenAsr = qwenAsrAvailable && window.MediaRecorder && navigator.mediaDevices?.getUserMedia;
  if (busy || !ready || (!Recognition && !canUseQwenAsr)) return;
  stopSpeech();
  el("mic").textContent = "Stop listening";
  el("audio-status").textContent = "Listening for your reply…";
  let microphone;
  let result;
  try {
    if (canUseQwenAsr) {
      try { microphone = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}}); }
      catch { if (!Recognition) throw new Error("Allow microphone access and try again."); }
    }
    result = await listenForReplyWithQwen(microphone);
  } catch (error) {
    const detail = providerError(error);
    result = {error:error.name === "NotAllowedError" ? "not-allowed" : "qwen-error", detail:error.name === "NotAllowedError" ? "Allow microphone access for this site, reload, and try again." : detail};
  } finally {
    microphone?.getTracks().forEach(track => track.stop());
    el("mic").textContent = "Use mic for one reply";
  }
  if (result.cancelled) { el("audio-status").textContent = "Listening stopped."; return; }
  if (result.error || !result.text.trim()) {
    el("audio-status").textContent = result.error === "no-speech"
      ? "No speech recognized. Try again or type a reply."
      : result.detail || recognitionError(result.error);
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
if (!Recognition && !(qwenAsrAvailable && window.MediaRecorder)) el("audio-status").textContent="Speech recognition is unavailable in this browser. Typed replies work.";
const startupHint = setTimeout(() => {
  if (!ready) status("The first load can take a minute. If this message stays here, refresh the page or try the local demo.");
}, 20_000);
try {
  await reset(false);
  const [tts, asr, qwen] = await Promise.all([
    fetch("/api/voice/tts", {cache:"no-store"}).catch(() => null),
    fetch("/api/voice/asr", {cache:"no-store"}).catch(() => null),
    fetch("/api/voice/qwen", {cache:"no-store"}).catch(() => null)
  ]);
  if (tts?.ok) fishVoiceAvailable = (await tts.json()).available === true;
  if (asr?.ok) qwenAsrAvailable = (await asr.json()).available === true;
  if (qwen?.ok) qwenReplyAvailable = (await qwen.json()).available === true;
  ready = true;
  status(qwenAsrAvailable ? "Ready · V2 · Qwen transcription" : Recognition ? "Ready · V2 · Browser speech recognition" : fishVoiceAvailable ? "Ready · V2 · Fish Audio voice" : "Ready · V2 Python build");
  if (!speech && !fishVoiceAvailable && Recognition) el("audio-status").textContent="Speech playback is unavailable in this browser. Typed replies work.";
  else if (qwenAsrAvailable && qwenReplyAvailable) el("audio-status").textContent="Qwen handles transcription and unrecognized questions only; normal account services remain scripted.";
  else if (qwenAsrAvailable) el("audio-status").textContent="Qwen transcription is enabled; unrecognized questions use the scripted fallback.";
  else if (qwenReplyAvailable) el("audio-status").textContent="Browser speech recognition is active; Qwen answers only unrecognized questions.";
  else if (Recognition) el("audio-status").textContent="Browser speech recognition is active. Qwen is not configured yet.";
} catch (err) {status(err.message);}
finally {clearTimeout(startupHint);}
busy = false;controls();
