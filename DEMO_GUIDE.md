# Step-by-step capstone demo

This guide shows the working no-billing project and clearly separates local evidence from CX Agent Studio results.

## Before the presentation

1. Use a computer with Python 3.10 or later and a browser.
2. Open the repository folder and double-click `RUN_DEMO.bat`. It starts a local web server and opens the demo at `http://127.0.0.1:8765/`. Keep the server window open. Stop it with Ctrl+C in that window after the presentation.
3. If the computer is not prepared, use the [hosted browser demo](https://harbour-trust-voice-capstone-10.vercel.app/). It runs the same packaged local Python builds in the browser.
4. Use only the fictional caller details shown in the demo. Never enter real bank or identity information.

## Presentation sequence

### 1. Introduce the project

Say: “This is a fictional bank account-services voice helpline. A root desk verifies the caller, then routes account requests to Account Service. The browser demo and the exported Python tools use the same project rules and fictional data.”

In the repository, show `helpline/` for the business rules, `studio/packages/` for the V1/V2 exports, and `studio/build.py` for the agent, tool, guardrail, callback, calendar, and evaluation definitions.

### 2. Show the complete balance call

1. In **Call desk**, click **New call** if an earlier conversation is still visible.
2. Click **Run example call**. The demo sends the fictional sequence `HT4102` → `14 June 1993` → `0042` → `yes` → `balance`.
3. Point out the verification prompts, the **18,420 rupees** balance, and the recorded handoff to **Instant Pay**.

For a live typed rehearsal, start a new call and enter those same five replies one at a time as the desk prompts. The details are fictional.

### 3. Show the V1/V2 regression results

1. Open **Regression suite**.
2. Click **Run both versions** and wait for the results.
3. Explain the actual browser-suite result: V1 baseline **51/53 (96.2%)**; revised V2 **53/53 (100%)**. The two retained V1 failures are S10 (unfamiliar crisis wording) and S16 (harm request with a person mentioned); V2 resolves them.

These are local browser regression results. They are not CX Agent Studio Evaluate scores.

### 4. Show guardrail evidence

1. In the repository folder, double-click `RUN_CHECKS.bat`.
2. Point out the guardrail section: **15/15** local probes across five categories—private identifiers, crisis support, grounded account replies, harm safety, and prompt security.
3. Open `evidence/local-guardrails.json` to show each trigger, harmless control, paraphrase, expected result, and observed result.

### 5. Show the calendar integration work

1. Open `evidence/calendar-endpoint.json`. It records a live GET to the GOV.UK calendar returning 83 England and Wales events, each with a date and title.
2. Explain that the exported Studio package includes an OpenAPI schema and a local fake response for deterministic package replay.
3. Be precise: the public endpoint and package references have been checked, but a live invocation from CX Agent Studio has not been verified.

### 6. Show the voice work honestly

The optional **Use microphone** control can accept a spoken reply when the browser supports speech recognition and the presenter grants microphone access. Typed replies remain available. `demo/HarbourTrust-offline.mp4` is a backup example; it does not replace the five required live Studio voice calls. Existing synthetic Windows-ASR probes achieved 4/5 expected outcomes; overlapping speech remains a known failure in `evidence/local-audio.json`.

## What is not yet demonstrated in Studio

The open Cloud project currently blocks writes and Studio preview reports a resource error. The official Studio Evaluate run, managed Team-numbered V1/V2 versions, Studio OpenAPI invocation, and five human-spoken Studio calls are therefore still pending. The current account/project state also requires billing attention. Do not present local browser scores as hosted Studio scores.

The final team number, member contributions, and any private course submission also need the team’s real details and action. Do not invent those details during the demo.
