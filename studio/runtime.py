"""Appended to each standalone Studio tool by the builder. CES injects context."""
def _utterance(ctx):
    content = ctx.user_content
    values = []
    for part in getattr(content, "parts", []) or []:
        if getattr(part, "text", None):
            values.append(part.text)
        elif getattr(part, "blob", None):
            values.append(part.blob.transcript() or "")
    return " ".join(values)

def _session(ctx):
    state = fresh()
    for key in state:
        if key in ctx.state:
            state[key] = ctx.state[key]
    for key in ("transfer_date","input_channel"):
        state[key] = ctx.state.get(key,"")
    return state

def _advance(ctx, allowed):
    current = _session(ctx)
    invocation = str(ctx.invocation_id)
    cached = ctx.state.get("last_result",{})
    if cached and ctx.state.get("last_invocation") == invocation:
        return cached
    if current["stage"] not in allowed and not current["handoff"]:
        return {"stage":current["stage"],"wrong_tool":True}
    def calendar():
        return tools.uk_bank_holidays({})
    desk = Desk(DIRECTORY, state=current, calendar=calendar)
    reply = desk.turn(_utterance(ctx))
    for k,v in current.items():
        ctx.state[k] = v
    result = {"say":reply,"stage":current["stage"],"verified":current["verified"],"handoff":current["handoff"]}
    ctx.state["last_result"] = result
    ctx.state["last_invocation"] = invocation
    return result
