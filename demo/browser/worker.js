import { loadPyodide } from "./vendor/pyodide/pyodide.mjs";
// Each message is processed on the same isolated Python interpreter.
const root = new URL("../../", self.location.href);
const runtime = new URL("vendor/pyodide/", self.location.href).href;
function progress(message) { self.postMessage({type:"progress",message}); }
async function file(path) {
  const res = await fetch(new URL(path, root));
  if (!res.ok) throw new Error("Could not load " + path);
  return new Uint8Array(await res.arrayBuffer());
}
async function start() {
  progress("Starting the Python runtime…");
  const py = await loadPyodide({indexURL:runtime});
  const files = ["helpline/__init__.py","helpline/desk.py","helpline/policy.py","helpline/tools.py","helpline/speech.py","helpline/fixtures.json","evaluation/__init__.py","evaluation/run.py","evaluation/catalog.py","studio/packages/HarbourTrust-V1.zip","studio/packages/HarbourTrust-V2.zip"];
  progress("Loading the fictional account data and V1/V2 builds…");
  await Promise.all(files.map(async path => {
    const data = await file(path);
    const dest = "/app/" + path;
    py.FS.mkdirTree(dest.slice(0, dest.lastIndexOf("/")));
    py.FS.writeFile(dest, data);
  }));
  try {
    const response = await fetch(new URL("/api/calendar", self.location.origin), {cache:"no-store"});
    if (response.ok) {
      const calendar = await response.json();
      if (["live","cache"].includes(calendar.source) && calendar.feed?.["england-and-wales"]?.events?.length) {
        py.FS.writeFile("/app/helpline/runtime-calendar.json", JSON.stringify({...calendar.feed,_source:calendar.source}));
      }
    }
  } catch {
    // session.py uses the repository's bundled snapshot when the endpoint is unavailable.
  }
  progress("Preparing the call desk…");
  const source = new TextDecoder().decode(await file("demo/browser/session.py"));
  py.runPython(source);
  return py;
}
const ready = start();
self.onmessage = async ({data}) => {
  try {
    const py = await ready;
    const response = py.globals.get("respond");
    try {
      self.postMessage({id:data.id,value:JSON.parse(response(data.action, data.text || ""))});
    } finally { response.destroy(); }
  } catch (error) {
    self.postMessage({id:data.id,error:"The helpline could not run. "+String(error.message || error).slice(-500)});
    console.error(error);
  }
};
