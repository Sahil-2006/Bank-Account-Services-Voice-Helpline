# Harbour Trust Bank Account Services Voice Helpline

Capstone Project 10 implements a fictional bank helpline for balances, statements and transfer limits. The root desk verifies the caller and passes account requests to Account Service. Both agents have privacy and crisis instructions. The Python rules and customer fixtures are shared between the offline desk and the Studio packages.

## Report and deliverables

[Open the live browser demo](https://harbour-trust-voice-capstone-10.vercel.app/). Select **Run example call** to see the verification and balance handoff, or open **Regression suite** to execute the V1 and V2 Python builds yourself. **Start voice call** runs a turn-by-turn spoken V2 call using the browser's speech recognition for microphone input. When the scripted desk marks a service question as unrecognized, the open Qwen3-0.6B model generates a short reply locally in the browser; it receives no account records or tools, and no Qwen API key is required. The model weights download on the first such question and are then cached by the browser. Normal banking services remain on deterministic Python rules. Fish Audio generates spoken desk replies when configured; browser speech synthesis is the fallback. Allow microphone access in Edge's site permissions (lock icon beside the address), reload, and start again. Use only the fictional caller details shown in the demo.

| File | Contents |
| --- | --- |
| [Project report](submission/Capstone10_Report.pdf) | Ten pages covering architecture, traceability, evaluation, guardrails, voice transcripts and limitations. Page 8 contains the actual Studio Build screenshot and a production browser call; page 9 shows the current 56-case browser replay. Page 10 marks the missing Studio evidence as illustrations. |
| [Requirements and Test Data](submission/Requirements%20and%20Test%20Data.xlsx) | The template headings, 15 user stories, all 30 PDF edge cases plus 18 supplementary checks, 56 transcript records and coverage checks. |
| [Team contribution note](submission/Contribution-note.md) | Four editable paragraphs awaiting the actual roster and individual contributions. |
| [Offline backup video](demo/HarbourTrust-offline.mp4) | A 49-second narrated balance call using actual local speech-recognition results and a fictional customer. For demo backup. |
| [V1 package](studio/packages/HarbourTrust-V1.zip) · [V2 package](studio/packages/HarbourTrust-V2.zip) | Studio-format archives containing both agents, Python tools, an OpenAPI calendar, guardrails and evaluation definitions. |

## Run one complete call

On Windows, double-click [RUN_DEMO.bat](RUN_DEMO.bat) to open the browser desk locally. Use the “Run example call” button for the balance handoff, or choose “Regression suite” and run both versions. Keep the server window open during the demo and press Ctrl+C in it to stop the server. Double-click [RUN_CHECKS.bat](RUN_CHECKS.bat) to run all four local check groups.

For a presentation sequence, expected outputs, and the Studio-only items that remain blocked, see the [step-by-step demo guide](DEMO_GUIDE.md).

Use Python 3.10 or later from the repository root. The text desk and regression runner use the standard library.

```sh
python -m helpline
```

Give each answer when the desk asks. Say **HT4102**, **14 June 1993**, **0042**, **yes**, then **balance**. The desk reports **18,420 rupees** and transfers the simulated call to **Instant Pay**. Calls use 10 November 2026 at 09:00 India time. Local handoff events and daily statement reservations are written in `.local/`. Use `--state-dir PATH` for a separate rehearsal ledger.

For a live local microphone rehearsal on Windows with an installed English (US) Windows speech recognizer, run the following with a headset. The script uses the system speech engine and Python. Saying **zero** requests a person. This local rehearsal and the browser voice call are speech interfaces to the simulated Python desk; neither places a telephone call.

```powershell
powershell.exe -NoProfile -File voice/start.ps1
```

The hosted demo reads `FISH_AUDIO_API_KEY` from the Vercel **Production** environment for Fish Audio speech synthesis. The key is never stored in source or exposed to the browser. To set or rotate it, use Vercel Project Settings → Environment Variables. If unavailable, browser speech synthesis is used. Qwen fallback replies use the open `Qwen3-0.6B` model in the browser through its ONNX conversion. The first unrecognized question downloads the model files from Hugging Face; generation then runs on the visitor's device without sending the question to a model API. No DashScope key or per-request Qwen API billing is used.

## What the evidence shows

| Check | Result |
| --- | --- |
| Local transcript suite, baseline | 46/56 (82.1%). Ten baseline misses are recorded in [the baseline evidence](evidence/local-v1.json). |
| Local transcript suite, revised | 56/56 (100%). Includes 29 golden and 27 scenario specifications. [Per-case results](evidence/local-v2.json). |
| Exported Python tools with a local Studio context double | V1 replayed 46/56; V2 passed 56/56. [Package replay](evidence/package-replay.json). |
| Local guardrail probes | 15/15 across five guardrails, including harmless controls and paraphrases. [Probe results](evidence/local-guardrails.json). |
| Synthetic audio through Windows ASR | 4/5 expected outcomes. Recognition of a request during overlapping speech failed. [Audio transcripts and replies](evidence/local-audio.json). |
| GOV.UK holiday endpoint | The Vercel API returns validated live data or a bundled cache. Local replay confirms date adjustment and a technical handoff if both sources fail. Studio OpenAPI invocation remains unverified. [Endpoint check](evidence/calendar-endpoint.json). |

```sh
python -m evaluation.run
python -m evaluation.guards
python -m evaluation.verify_packages
python -m unittest -v evaluation.test_invariants
```

To reproduce the acoustic probes on Windows, run `powershell.exe -NoProfile -File evaluation/audio_probe.ps1 -OutputDir .local/audio`, followed by `python -m evaluation.audio_results .local/audio/recognition.json`. The baseline uses free dictation. The revised run uses the voice client’s vocabulary plus dictation. The probe creates WAV files from synthetic voices without opening a microphone. The report PDF can be regenerated with `python -m submission.build_report` in an environment with ReportLab.

## Use CX Agent Studio

The native builder screenshot shows the Harbour Trust root desk and Account Service agents in project `harbour-trust-voice-helpline`, region `us`. A completed-scenario notification is visible, but no detailed result pane was captured, so no Studio score is claimed. The available billing notice says trial activation requires prepayment; an active billing link to this project has not been verified. Hosted V1/V2 Evaluate scores, managed version records, five human-spoken Studio calls and Google Classroom submission remain pending. Team number and individual contributions also await confirmation. The archives use **RosterPending** as a temporary label.

The initial import omitted the holiday API tool. The rebuilt archives reference included OpenAPI schema and fake-response files, and the package verifier checks those references and executes the fake calendar responses. V2 passes all 56 local replays; hosted acceptance of the correction remains unverified.

The native captures record the configured Build canvas and the billing-related Evaluate access state. A completed-scenario notification is visible in the latest Build capture, but no detailed results are shown. [Current Studio Build capture](evidence/studio/build-agent-flow.png) · [Earlier imported flow](evidence/studio/imported-agent-flow.jpg) · [Evaluate access state](evidence/studio/evaluation-access.jpg)

With a billing-enabled course project, the CES API enabled, a signed-in `gcloud` CLI and suitable CES permissions, the publisher builds team-named packages from the source, imports a new application, creates the suite, saves V1, evaluates it, updates its tools, saves V2 and evaluates it. It sets the external calendar fake for the evaluated snapshots and restores live calendar mode on the draft. Keep the generated local checkpoint to resume a run. Hosted service use can incur Google Cloud charges.

```sh
python -m studio.publish --project YOUR_PROJECT_ID --region us --preflight
python -m studio.publish --project YOUR_PROJECT_ID --region us --team YOUR_TEAM_NUMBER
```

Alternatively, build a team-named archive for console import. Clone with Git tags so the V1 builder can load the baseline implementation.

```sh
python -m studio.build --team YOUR_TEAM_NUMBER --version V2 --output HarbourTrust-V2.zip
```

For the live assessment, open the team's Studio application. Capture the full-screen Versions pane and the V1/V2 Evaluate results with visible team names. Speak the five calls from report page 6 into the console. Add the actual transcripts and screenshots, update the report filename to `Team<NN>_Capstone10_Report.pdf` and enter the confirmed roster and contributions in the private submission copy.

## Service boundaries

Customer and account records are fictional. Handoffs record a destination and routing tags. The project has no real bank, telephone queue or statement delivery backend. The local ledger enforces the same-day rule across calls. Studio fixtures model a previously sent statement. Only the fictional BankWire UK clearing leg consults the public England and Wales calendar. Live calendar data is validated; a bundled snapshot is used if the endpoint is unavailable, and a technical handoff occurs if both sources fail.

The voice pack targets English. The offline grammar recognizes a limited set of spoken dates and amounts. The provider’s native guardrail ordering, voice interruptions and managed evaluation metrics still require a hosted test.

[Studio export specification](https://docs.cloud.google.com/gemini-enterprise-cx/cx-agent-studio/reference/export) · [Studio evaluations](https://docs.cloud.google.com/gemini-enterprise-cx/cx-agent-studio/evaluation) · [GOV.UK bank holidays](https://www.gov.uk/bank-holidays)
