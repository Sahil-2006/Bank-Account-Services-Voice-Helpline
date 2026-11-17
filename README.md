# Harbour Trust Bank Account Services Voice Helpline

Capstone Project 10 implements a fictional bank helpline for balances, statements and transfer limits. The root desk verifies the caller and passes account requests to Account Service. Both agents have privacy and crisis instructions. The Python rules and customer fixtures are shared between the offline desk and the Studio packages.

## Report and deliverables

[Open the live browser demo](https://harbour-trust-voice-capstone-10.vercel.app/). Select **Run example call** to see the verification and balance handoff, or open **Regression suite** to execute the V1 and V2 Python builds yourself. Typed replies run in the browser. Speech input depends on the browser's speech service and microphone permission. The demo uses a fixed holiday fixture and remembers statement reservations until the page reloads.

| File | Contents |
| --- | --- |
| [Project report](submission/Capstone10_Report.pdf) | Ten pages covering architecture, traceability, evaluation, guardrails, voice transcripts and limitations. Pages 8 and 9 contain genuine browser screenshots. Page 10 illustrates the three outstanding Studio captures. |
| [Requirements and Test Data](submission/Requirements%20and%20Test%20Data.xlsx) | The template headings, 15 user stories, 48 edge cases, 55 fictional data rows and coverage checks. |
| [Team contribution note](submission/Contribution-note.md) | Four editable paragraphs awaiting the actual roster and individual contributions. |
| [Offline backup video](demo/HarbourTrust-offline.mp4) | A 49-second narrated balance call using actual local speech-recognition results and a fictional customer. For demo backup. |
| [V1 package](studio/packages/HarbourTrust-V1.zip) · [V2 package](studio/packages/HarbourTrust-V2.zip) | Studio-format archives containing both agents, Python tools, an OpenAPI calendar, guardrails and evaluation definitions. |

## Run one complete call

Use Python 3.10 or later from the repository root. The text desk and regression runner use the standard library.

```sh
python -m helpline
```

Give each answer when the desk asks. Say **HT4102**, **14 June 1993**, **0042**, **yes**, then **balance**. The desk reports **18,420 rupees** and transfers the simulated call to **Instant Pay**. Calls use 10 November 2026 at 09:00 India time. Local handoff events and daily statement reservations are written in `.local/`. Use `--state-dir PATH` for a separate rehearsal ledger.

For a live local microphone rehearsal on Windows with an installed English (US) Windows speech recognizer, run the following with a headset. The script uses the system speech engine and Python. Saying **zero** requests a person.

```powershell
powershell.exe -NoProfile -File voice/start.ps1
```

## What the evidence shows

| Check | Result |
| --- | --- |
| Local transcript suite, baseline | 51/53 (96.2%). The two failures are preserved in [the baseline evidence](evidence/local-v1.json). |
| Local transcript suite, revised | 53/53 (100%). Includes 29 golden and 24 scenario specifications. [Per-case results](evidence/local-v2.json). |
| Exported Python tools with a local Studio context double | V1 reproduced both failures. V2 passed all 53 cases. [Package replay](evidence/package-replay.json). |
| Local guardrail probes | 15/15 across five guardrails, including harmless controls and paraphrases. [Probe results](evidence/local-guardrails.json). |
| Synthetic audio through Windows ASR | 4/5 expected outcomes. Recognition of a request during overlapping speech failed. [Audio transcripts and replies](evidence/local-audio.json). |

```sh
python -m evaluation.run
python -m evaluation.guards
python -m evaluation.verify_packages
python -m unittest -v evaluation.test_invariants
```

To reproduce the acoustic probes on Windows, run `powershell.exe -NoProfile -File evaluation/audio_probe.ps1 -OutputDir .local/audio`, followed by `python -m evaluation.audio_results .local/audio/recognition.json`. The baseline uses free dictation. The revised run uses the voice client’s vocabulary plus dictation. The probe creates WAV files from synthetic voices without opening a microphone. The report PDF can be regenerated with `python -m submission.build_report` in an environment with ReportLab.

## Use CX Agent Studio

The project currently has no hosted run. The signed-in account’s accessible projects had billing disabled, and the selected project's regional CES endpoint returned HTTP 403. Team number and member details are pending. The two downloadable archives use **RosterPending** as a temporary label. Google Classroom submission, native version screenshots, hosted evaluation scores and five human-spoken Studio calls remain outstanding.

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

Customer and account records are fictional. Handoffs record a destination and routing tags. The project has no real bank, telephone queue or statement delivery backend. The local ledger enforces the same-day rule across calls. Studio fixtures model a previously sent statement. Only the fictional BankWire UK clearing leg consults the public England and Wales calendar. A failed calendar lookup preserves the account result and produces a short availability message.

The voice pack targets English. The offline grammar recognizes a limited set of spoken dates and amounts. The provider’s native guardrail ordering, voice interruptions and managed evaluation metrics still require a hosted test.

[Studio export specification](https://docs.cloud.google.com/gemini-enterprise-cx/cx-agent-studio/reference/export) · [Studio evaluations](https://docs.cloud.google.com/gemini-enterprise-cx/cx-agent-studio/evaluation) · [GOV.UK bank holidays](https://www.gov.uk/bank-holidays)
