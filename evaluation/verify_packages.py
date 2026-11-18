"""Check archive links and replay exported Python with a minimal CES context double."""
import contextlib
import io
import json
from types import SimpleNamespace
from zipfile import ZipFile
from evaluation.catalog import ROOT, CASES
from evaluation.run import CALENDAR
from helpline.policy import CRISIS, TERMS
from studio.build import TOOLS

def verify(path):
    with ZipFile(path) as pack:
        assert pack.testzip() is None
        resources={f.split("/",1)[1]:pack.read(f).decode() for f in pack.namelist()}
    app=json.loads(resources["app.json"])
    def resources_in(group):
        return [json.loads(value) for key,value in resources.items() if key.startswith(group+"/") and key.endswith(".json")]
    agents=resources_in("agents");tools=resources_in("tools");rail=resources_in("guardrails")
    tool_names={r["displayName"] for r in tools}
    agent_names={r["displayName"] for r in agents}
    assert len(agents)==2 and app["rootAgent"] in agent_names
    assert set(app["guardrails"])=={r["displayName"] for r in rail}
    assert len(resources_in("evaluations"))==len(CASES)
    for agent in agents:
        prompt=resources[agent["instruction"]]
        assert all(x in prompt for x in ("Role","Persona","Context","Task","Constraints",CRISIS))
        assert set(agent["tools"])<=tool_names and set(agent["childAgents"])<=agent_names
        for callback in agent["afterToolCallbacks"]+agent["afterAgentCallbacks"]:
            compile(resources[callback["pythonCode"]],callback["pythonCode"],"exec")
    library={}
    for tool in tools:
        pf=tool.get("pythonFunction")
        if pf:library[tool["displayName"]]=compile(resources[pf["pythonCode"]],pf["pythonCode"],"exec")
        api=tool.get("openApiTool")
        if api:
            schema=json.loads(resources[api["openApiSchema"]])
            assert schema["paths"]["/bank-holidays.json"]["get"]["operationId"]==api["name"]
            fake_path=tool["toolFakeConfig"]["codeBlock"]["pythonCode"]
            fake={}
            exec(compile(resources[fake_path],fake_path,"exec"),fake)
            assert fake["fake_tool_call"](None,{},SimpleNamespace(variables={}))==CALENDAR
            unavailable=SimpleNamespace(variables={"calendar_unavailable":True})
            assert fake["fake_tool_call"](None,{},unavailable)=={}
    hooks={}
    exec(resources[agents[0]["afterToolCallbacks"][0]["pythonCode"]],hooks)
    failures=[];failed_cases=[]
    for case in CASES:
        state={}
        sdk=SimpleNamespace(state=state,variables=state,invocation_id="",user_content=None)
        current="id"; last="";said=[]
        for i,turn in enumerate(case["turns"]):
            sdk.invocation_id=str(i+1);sdk.user_content=SimpleNamespace(parts=[SimpleNamespace(text=turn)])
            tool_name=next(name for name,(_,stages) in TOOLS.items() if current in stages)
            feed=CALENDAR if case["calendar"]=="ok" else {}
            env={"context":sdk,"tools":SimpleNamespace(uk_bank_holidays=lambda _:feed)}
            exec(library[tool_name],env)
            result=env[tool_name]()
            # Repeat invocation delivers the cached reply without consuming another retry.
            assert env[tool_name]()==result
            with contextlib.redirect_stdout(io.StringIO()):
                hooks["after_tool_callback"](None,{},sdk,result)
            last=result["say"];said.append(last);current=result["stage"]
        handoff=state.get("handoff",{})
        ok=last==case["expected"] if case["exact"] else case["expected"].lower() in last.lower()
        ok &= handoff.get("reason","")==case["reason"] and handoff.get("channel","")==case["channel"]
        ok &= state["intent_tag"]==case["intent"] and bool(state.get("logged"))==bool(handoff)
        ok &= sum(x.count(TERMS) for x in said)==int(bool(case["channel"]))
        if not ok:
            failures.append(case["id"])
            failed_cases.append({"id":case["id"],"title":case["title"]})
    return {"package":path.name,"cases":len(CASES),"passed":len(CASES)-len(failures),"failures":failures,"failed_cases":failed_cases}

if __name__=="__main__":
    results=[verify(ROOT/"studio/packages"/f"HarbourTrust-{v}.zip") for v in ("V1","V2")]
    assert results[0]["failures"] and not results[1]["failures"],results
    (ROOT/"evidence/package-replay.json").write_text(json.dumps(results,indent=2)+"\n",encoding="utf-8")
    print(results)
