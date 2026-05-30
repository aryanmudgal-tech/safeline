# Safeline Chapter 1 Handover

Date: 2026-05-30

Primary workspace: `/Users/aryanmudgal/Documents/Safeline`

Primary implementation repo: `/Users/aryanmudgal/Documents/Safeline/safeline1`

## Current Working State

Safeline now has the core officer workflow working end to end:

1. Officer calls the Twilio number.
2. Twilio routes the call into the Pipecat Cloud agent.
3. The voice agent conducts the incident documentation conversation.
4. The agent creates a six-digit access code and reads it to the officer.
5. The agent generates structured reports from the transcript.
6. The agent posts the generated reports to the review portal.
7. Officer opens the review portal, enters the six-digit code, edits the reports, and approves them.

The user has confirmed the live call works, the agent gives the access code, the portal accepts the code, and the report is visible.

## Main System Pieces

### Voice Agent

Location: `safeline1/server/police_agent.py`

The existing voice conversation implementation from `safeline1` is the base going forward. It is strong because it already:

- Handles real spoken conversation instead of only form filling.
- Uses LLM calls to interpret the officer's narration.
- Maintains a working Pipecat/Twilio call flow.
- Can generate reports after the conversation.
- Now creates and speaks the same six-digit access code used by the portal.

### Report Store

Location: `safeline1/server/report_generator.py`

The report store now supports:

- Six-digit access code generation.
- Pending incidents before reports are finished.
- Lookup by either incident id or six-digit code.
- File-backed persistence under `safeline1/server/data/incidents/` by default.
- Immutable AI draft storage.
- Officer-edited version storage.
- Field-level diffs after approval.
- Statuses such as `generating`, `pending_review`, `approved`, and `generation_failed`.

### Review Portal API

Location: `safeline1/server/review_ui/api.py`

Important endpoints:

```http
POST /api/reports/save
GET /api/reports/{6-digit-code}
POST /api/reports/{6-digit-code}/approve
GET /api/reports/{6-digit-code}/diff
GET /api/reports/{6-digit-code}/evaluate
GET /api/incidents
```

The deployed voice agent calls:

```http
POST {REVIEW_UI_URL}/api/reports/save
```

with a payload shaped like:

```json
{
  "code": "813562",
  "incident_id": "INC-20260530-115023",
  "officer_name": "Officer Martinez",
  "officer_badge": "4521",
  "generated_at": "2026-05-30T11:50:23",
  "reports": {
    "incident_report": {},
    "arrest_report": {},
    "use_of_force": {}
  },
  "transcript": "full conversation transcript"
}
```

### Review Portal UI

Location: `safeline1/server/review_ui/index.html`

The UI now supports:

- Six individual digit boxes for the access code.
- Query param loading, for example `/?code=813562`.
- Error state for invalid or missing codes.
- Pending/generating state while the agent is still writing reports.
- Editable report sections.
- Approve all reports.
- Transcript and diff/evaluation surfaces.

## Deployment State

Pipecat Cloud:

- Organization: `safeline`
- Agent: `flower-bot`
- Secret set: `flower-bot-secrets`
- Agent profile: `agent-1x`
- Krisp VIVA: enabled for tel
- Current deployment was updated after the review portal URL was fixed.

Twilio:

- TwiML service host was updated to the `safeline` Pipecat Cloud namespace.
- The call path is now connected to the deployed Pipecat agent.

Review portal exposure:

- Local portal runs on `127.0.0.1:8080`.
- Public access currently uses ngrok and is configured through `REVIEW_UI_URL`.
- Important caveat: the free/random ngrok URL can change if ngrok stops, the laptop sleeps, or the tunnel restarts. For demo reliability, use a reserved/static ngrok domain and keep `REVIEW_UI_URL` stable.

## Environment Notes

Secrets live in `.env` files and Pipecat Cloud secrets. Do not commit real `.env` files.

Important environment values:

```bash
REVIEW_UI_PORT=8080
REVIEW_UI_URL=https://<public-review-portal-url>
OPENAI_API_KEY=...
GRADIUM_API_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=...
CEKURA_API_KEY=...
```

After changing `REVIEW_UI_URL`, update Pipecat Cloud secrets and redeploy:

```bash
cd /Users/aryanmudgal/Documents/Safeline/safeline1/server
pc cloud secrets set flower-bot-secrets --file ../.env --skip
pc cloud deploy --config-file pcc-deploy.toml --yes
```

## What Was Verified

Verified manually:

- Local review portal returns `200` at `http://127.0.0.1:8080/`.
- Public ngrok portal returns `200`.
- Public `/api/incidents` returns `200`.
- Public `POST /api/reports/save` returns `200`.
- Public `GET /api/reports/{code}` returns `200`.
- Pipecat Cloud deployment is ready.
- Live call provides an access code.
- Portal lookup by that access code displays the report.

## Known Caveats

- The current public portal depends on ngrok staying alive.
- If ngrok changes, the deployed voice agent will keep posting to the old URL until Pipecat secrets are updated and the agent is redeployed.
- The review portal is currently unauthenticated. The six-digit code is the only access control. That is fine for hackathon/demo flow, but not production.
- The report approval flow stores officer edits, but the deeper self-evaluation loop still needs to be formalized and automated.
- The portal and deployed agent communicate over HTTP, not shared storage, which is good for deployment, but means the review UI must be reachable from Pipecat Cloud.

## Chapter 2 Goal: Self-Evaluation And Tangible Improvement

The next phase should not be framed as "make the agent better" in a vague way. The concrete goal is:

> Reduce the amount of officer editing required while increasing report completeness, groundedness, legal/reporting accuracy, and professional narrative quality.

That gives us measurable improvement targets.

## What The Improvement Should Be On

### 1. Required Field Completeness

The agent should increasingly fill the required fields for each report type:

- Incident report: date, time, location, involved parties, narrative, disposition, witnesses, evidence.
- Arrest report: probable cause, charges/reason for arrest, subject identity, custody timeline, search/transport details.
- Use-of-force report: force type, reason for force, resistance level, warnings, de-escalation attempts, injuries, medical aid, supervisor notification.

Metric:

```text
required_fields_completed / required_fields_total
```

### 2. Groundedness

The report should only contain facts supported by the transcript. If the officer did not say something, the model should leave it null or ask a follow-up question.

Metric:

```text
fields_supported_by_transcript / non_empty_fields
```

### 3. Professional Police Narrative Quality

The agent should convert casual spoken language into objective report language without inventing facts or sanitizing away important details.

Example input:

```text
Joshua Kumar had a knife. My partner and I removed the knife from him.
He resisted, we deployed Tasers, handcuffed him, and took him into custody.
```

Weak report language:

```text
Officers used brutal force to take him down.
```

Better report language:

```text
Officers observed Joshua Kumar armed with a knife. After commands and attempts
to gain compliance, officers deployed conducted electrical weapons due to the
subject's continued resistance and the immediate safety risk. Once the subject
was controlled, officers handcuffed him and transported him to custody.
```

The evaluator should check that the narrative is:

- Chronological.
- Objective.
- Specific about what force was used.
- Clear about why force was used.
- Clear about the subject's resistance or threat.
- Free of inflammatory phrasing such as "brutal force" unless directly quoting someone.

### 4. Use-of-Force Justification

Use-of-force reports need special treatment. The agent should not just say "Taser used." It should capture:

- What threat existed.
- Whether the subject was armed.
- Whether commands were given.
- Whether de-escalation was attempted.
- What resistance occurred.
- Why that force option was selected.
- How many Taser deployments/cycles occurred, if known.
- Whether the subject was injured.
- Whether medical evaluation was offered or provided.
- Whether a supervisor was notified.

Metric:

```text
force_justification_score from 0-5
```

### 5. Follow-Up Question Quality

The voice agent should ask fewer but better follow-up questions. The improvement is not "ask more questions." It is "ask the missing high-value question at the right time."

For the Joshua Kumar style scenario, good follow-ups would be:

- "Was Joshua Kumar armed with a knife when officers arrived, or did he pick it up later?"
- "Did officers give verbal commands before deploying the Taser?"
- "How many Taser deployments or cycles were used?"
- "Was Joshua Kumar injured, and was medical aid provided?"
- "What charge or custody reason should be listed?"

Metrics:

```text
missing_critical_fields_after_call
follow_up_questions_that_filled_required_fields / total_follow_up_questions
```

### 6. Report Type Selection

The agent should correctly decide which reports are required.

For an armed subject taken into custody with Taser deployment, the expected reports are probably:

- Incident report.
- Arrest report.
- Use-of-force report.

Metric:

```text
correct_report_types_selected / expected_report_types
```

### 7. Officer Edit Reduction

The strongest real-world metric is how much the officer has to change before approval.

Metrics:

```text
field_correction_rate = corrected_fields / generated_fields
narrative_edit_distance
approval_time_seconds
repeat_error_rate by correction category
```

## Proposed Self-Evaluation Loop

### Loop A: Offline Scenario Evaluation

Build a dataset of test incidents:

- Transcript.
- Expected report types.
- Expected required fields.
- Expected high-risk facts.
- Rubric scores.

Run the current agent/report generator against the dataset and score every output. Cekura can be used here as the evaluator runner and scoreboard.

### Loop B: Online Officer Correction Learning

Every approved portal edit becomes labeled data:

```json
{
  "transcript": "...",
  "report_type": "use_of_force",
  "field": "force_reason",
  "ai_value": "subject was noncompliant",
  "officer_value": "subject was armed with a knife and advanced toward officers",
  "correction_category": "under-specified threat"
}
```

This is already partially supported by the diff storage. The next step is to classify edits into a correction taxonomy.

### Loop C: Retrieval Into Generation

When a new transcript is similar to prior corrected incidents, retrieve the relevant corrections and inject them into the report-generation prompt as examples.

This already exists at the seed level through `server/improvement/correction_store.py`; Chapter 2 should make it more measurable and report-specific.

### Loop D: Pre-Submission Self-Check

Before reports are saved to the portal, run a self-check evaluator:

- Are required fields missing?
- Are any fields unsupported by transcript?
- Does use-of-force justification include threat, resistance, force type, injuries, and medical aid?
- Should the agent ask one more follow-up question before generating?

If critical fields are missing during the call, the agent should ask. If the call is already over, the portal should show those fields as missing instead of pretending the report is complete.

## Cekura's Role

Cekura should be used to prove improvement over time:

1. Create a benchmark set of transcripts.
2. Run baseline report generation.
3. Score baseline outputs with Cekura evaluators.
4. Add self-checks, better prompts, correction retrieval, and follow-up policy.
5. Run the same benchmark again.
6. Show score deltas.

The tangible improvement should be visible as:

- Higher completeness score.
- Lower hallucination score.
- Higher use-of-force justification score.
- Lower officer edit distance.
- Fewer missing critical fields.
- Faster approval.

## Recommended Chapter 2 Implementation Order

1. Create a small benchmark dataset with 8-12 realistic police documentation calls.
2. Add at least 3 hard use-of-force scenarios, including the Joshua Kumar armed-subject/Taser/custody scenario.
3. Add evaluator rubrics for report completeness, groundedness, report type selection, use-of-force justification, and narrative professionalism.
4. Store evaluator scores beside each incident.
5. Add correction taxonomy labels to officer edits.
6. Improve the report-generation prompt using retrieved corrections and explicit use-of-force checklists.
7. Add a pre-save self-check that flags missing critical facts.
8. Compare before/after scores in a simple results table.

## Demo Story For Next Chapter

The strongest demo is:

1. Run the baseline on a scenario.
2. Show that the first report misses or weakly describes a key fact.
3. Officer edits the report in the portal.
4. The system captures that edit as labeled data.
5. Run a similar scenario.
6. Show the next report is more complete, more grounded, and needs fewer edits.

That is the clearest way to show that Safeline is not just a voice report writer. It is a report writer with a measurable improvement loop.
