# Project Briefing: Law Enforcement Voice Documentation Agent
## Cekura + Daily Voice Agents Hackathon (May 30, 2026, YC Office, SF)

---

# 1. WHAT WE ARE BUILDING

## One-Sentence Pitch
A voice agent that police officers call after any incident to describe what happened in natural conversation; the agent asks targeted follow-up questions, then generates all required documentation (incident reports, arrest reports, use-of-force reports) in parallel, which the officer reviews, edits, and approves. Every edit makes the agent smarter.

## Why This Matters
Police officers spend 3-4+ hours per shift on paperwork. 96% of officers say heavy reporting demands keep them away from higher-value tasks like community safety. 65% of police departments reported personnel shortages in early 2026. Documentation is the bottleneck.

## The Competitor: Axon Draft One
Axon (the body camera company) has a product called Draft One that generates police reports from body camera audio. It has processed 100,000+ reports. However, it has four critical weaknesses that create our opportunity:

1. **No transparency.** Draft One erases the initial AI draft after the officer exports it. There is no record of what the AI wrote vs. what the officer changed. The EFF published a major investigation calling this out.
2. **Hallucination from ambient audio.** In one documented case, a Disney movie playing in the background caused the AI to write that an officer had "shapeshifted into a frog." Body cam audio is noisy, unstructured, and unreliable as a sole input.
3. **No active gap-filling.** Draft One passively summarizes whatever audio exists. If the body cam didn't capture a conversation, that information is simply missing from the report.
4. **No improvement over time.** Each report is generated independently. The system does not learn from officer corrections.

## Our Four Differentiators
1. **Active conversation, not passive capture.** The officer talks TO our agent. The agent asks targeted follow-up questions when it detects gaps. No hallucination from background audio because there is no background audio. The officer is speaking directly and intentionally.
2. **Full edit transparency and audit trail.** We track every diff between the AI draft and the officer's final version. The original AI draft is permanently preserved. Every document carries metadata showing which parts were AI-generated vs. officer-written. This directly addresses the EFF concerns and emerging state regulations.
3. **Self-improving.** A three-layer auto-improvement system. The agent gets measurably better from every officer correction. Axon Draft One does not have this.
4. **Multi-document generation.** Draft One generates a single narrative. Our sub-agents generate the incident report, arrest report, use-of-force documentation, and any supplementary reports simultaneously from the same conversation.

---

# 2. HACKATHON CONTEXT

## Event Details
- **Date**: May 30, 2026
- **Location**: YC Office, San Francisco
- **Build time**: ~7 hours
- **Prize**: Guaranteed YC Interview + sponsor judges' prizes

## Hackathon Themes
1. Leveraging/customizing SOTA open-weight models
2. Infrastructure and network optimization
3. Auto-improvement harness

Key quote from organizers: "We aren't just looking for the best-sounding voice; we are looking for the best system."

## Sponsors and How Each Fits

### NVIDIA (Intelligence Layer)
- **Nemotron 3 Super (120B, 12B active params)**: The orchestrator brain. Conducts the conversation, asks follow-up questions, extracts entities. Hosted via NIM API at build.nvidia.com (OpenAI-compatible endpoint).
- **Nemotron 3 Nano (30B, 3B active params)**: The sub-agent workers. Generate individual report documents from the conversation transcript. Lightweight and fast.
- **Nemotron Speech ASR**: Real-time speech-to-text. If not available as hosted endpoint, Deepgram is the fallback.
- **Magpie TTS**: Text-to-speech for the agent's voice. If not available as hosted endpoint, Cartesia or ElevenLabs is the fallback.
- **NeMo Customizer**: LoRA fine-tuning for the Layer 3 auto-improvement.
- **NeMo Curator**: Data curation for fine-tuning dataset preparation.
- **NeMo Evaluator**: Benchmarking fine-tuned vs. base models.

### Daily / Pipecat (Voice Orchestration)
- **Pipecat**: Open-source framework that orchestrates the full voice pipeline (VAD, ASR, LLM, TTS). Handles streaming, interruptions, turn detection, and frame-by-frame audio processing.
- **Pipecat Flows**: State machine framework for structured conversation management. We use this to manage the phases of the conversation (greeting, open narrative, report suggestion, gap-filling, completion).
- **Pipecat SmartTurn**: ML-based turn detection model that runs on audio data. Used as a fallback turn detection mechanism during Q&A.
- **Daily WebRTC**: Audio transport layer between Twilio and Pipecat.

### Twilio (Telephony)
- **Phone number**: The officer calls this number to reach the agent.
- **WebSocket Media Streams**: Twilio receives the call, opens a WebSocket to our server, and streams audio in real time.
- **DTMF detection**: Twilio forwards keypad presses (the # key) via WebSocket. This is our primary turn detection mechanism.
- **SMS**: Sends the officer a link to review generated documents.

### AWS (Infrastructure)
- **ECS Fargate**: Hosts the Pipecat pipeline container.
- **DynamoDB**: Stores incident records, officer corrections, case state, analytics data.
- **S3**: Stores documents (AI drafts, officer-approved versions, diffs), conversation transcripts, audio recordings.
- **Lambda + EventBridge**: Handles async tasks (document generation, notifications, scheduled follow-ups).
- **Bedrock Knowledge Bases**: Stores report templates, legal references, force continuum definitions, charge descriptions.
- **SES/SNS**: Email/SMS notifications to officers and supervisors.

### Cekura (Evaluation and Auto-Improvement)
- **Cekura Pipecat SDK**: Captures every conversation transcript, tool calls, recordings, and metadata. Provides observability into the voice pipeline.
- **Custom evaluators**: We define five evaluation metrics (report completeness, extraction accuracy, narrative faithfulness, cross-document consistency, question coverage).
- **Simulation scenarios**: Pre-built test scenarios with simulated callers for regression testing.
- **LLM judge tuning**: Tune evaluation prompts against real call recordings until judges match officer-level agreement.
- **Regression testing**: Full scenario suite runs before any prompt or model update is deployed. If any test case fails, the update is blocked.

---

# 3. THE COMPLETE USER WORKFLOW

## Stage 0: Department Onboarding (Setup)
1. A Twilio phone number is provisioned for the department.
2. An officer roster is loaded (badge numbers, names, ranks, units, supervisors). For the hackathon, this is a mock JSON file.
3. A department profile is configured (jurisdiction, state-specific reporting requirements, notification recipients, report templates).
4. Officers get a brief training: "Call this number after any incident, describe what happened, press # when done, review the reports we send you."

## Stage 1: Officer Initiates the Call
The incident has occurred. The officer has handled the situation (arrests, medical attention, scene secured). Now they need to document.

**Option A (primary):** Officer dials the Twilio number from their phone. Twilio receives the call, opens a WebSocket to our Pipecat server, and the agent answers.

**Option B (fallback):** Officer opens a web app and enters voice mode. Same Pipecat pipeline, different transport (Daily WebRTC in browser instead of Twilio telephony).

The agent greets the officer and asks for their badge number. Looks up the officer in the roster, confirms identity, and auto-populates the "reporting officer" fields across all documents.

## Stage 2: The Conversation

### Phase 1: Open Narrative
The agent says: "Go ahead, tell me what happened. Press pound when you are done."

The officer describes the incident in their own words, in whatever order feels natural. The agent listens without interrupting. There is no voice activity detection (VAD) active for turn purposes in this phase. The officer can pause, backtrack, restart. The only signal that ends this phase is the officer pressing # on their keypad.

During this phase, the agent is silently extracting entities from the real-time transcript: names, times, locations, actions taken, force used, arrests, charges, witnesses, evidence, injuries, vehicles.

### Report Suggestion
When # is pressed, the agent transitions immediately. Based on extracted entities, it suggests which report types to generate:

"Based on what you described, I recommend generating an incident report and an arrest report. I also noticed you mentioned using physical force to restrain the suspect, so a use-of-force report would be needed as well. Should I generate all three, or would you like to adjust?"

The officer confirms or modifies. This decision is captured as labeled training data (what the agent suggested vs. what the officer approved). Over time, the agent's suggestions improve.

### Phase 2: Targeted Gap-Filling (Q&A)
The agent now asks specific questions to fill gaps across all approved report types. It asks ONE question at a time, prioritized by legal importance:

1. Legally critical fields first (Miranda, force justification, charges)
2. Identity fields (suspect name, victim name, witness contacts)
3. Timeline fields (exact times, sequence of events)
4. Evidence and scene details
5. Administrative details

The agent asks a question. It automatically starts listening. The officer answers and presses # when done. The agent processes the answer, updates its extraction, and asks the next question. SmartTurn runs as a fallback: if the officer doesn't press # but 5 seconds of silence elapse after SmartTurn detects end-of-turn, the agent proceeds anyway.

At any point, the officer can say "that's all I have to report" to end the entire conversation immediately.

### Why DTMF (# key) Instead of Pure Voice Detection
1. Police officers are trained on push-to-talk radio protocols. Pressing a key to signal "I'm done" is muscle memory for this user group.
2. The hackathon demo will be in a noisy environment (YC office with other teams). Voice activity detection can misfire with background noise. DTMF is a digital signal, completely immune to audio noise.
3. DTMF turn detection has zero latency. The moment # is pressed, the agent knows instantly. No waiting for silence thresholds.

## Stage 3: Document Generation
The conversation ends. The orchestrator agent has a complete transcript and structured entity extraction. It dispatches to parallel specialist sub-agents:

- **Incident Report Agent** (always): Generates the chronological incident narrative.
- **Arrest Report Agent** (if arrest occurred): Structures suspect information, charges, evidence, Miranda documentation.
- **Use-of-Force Report Agent** (if force used): Writes the detailed force account following force continuum framework.
- **Accident Report Agent** (if vehicle involved): Structures vehicle, road conditions, injuries.

Each sub-agent runs on Nemotron 3 Nano (lightweight, fast) and receives: the full transcript, the entity extraction, the department's template for its document type, and relevant DSPy few-shot examples from past corrections.

All sub-agents run in parallel using async. Target: all documents ready within 60-90 seconds.

A consistency checker runs after all documents are generated, cross-referencing timestamps, names, and facts across documents. Inconsistencies are flagged.

The agent says: "Your reports are ready. I have sent you a link to review them." An SMS is sent via Twilio with the review link.

## Stage 4: Officer Review and Approval
The officer opens a web interface (linked from SMS). They see:

1. Each generated report as an editable form (field by field)
2. The conversation transcript alongside, with linked evidence (click a field to see which part of the conversation supports it)
3. An AI transparency badge: "Draft generated by AI from officer's verbal account"
4. An "Approve" button per document

The officer edits whatever needs changing and approves each document.

## Stage 5: Edit Tracking and Audit Trail
When the officer approves:

1. **The original AI draft is permanently preserved.** Unlike Axon Draft One, we never erase it.
2. **A JSON diff is computed** between the original AI draft and the officer's final version. Every field-level change is captured: what the AI wrote, what the officer changed it to, the timestamp, and the correction category (entity correction, narrative rewrite, missing field added, legal language fix, etc.).
3. **AI disclosure metadata is attached** to the final document showing which parts were AI-generated vs. officer-written.
4. **The correction feeds the auto-improvement loop** (see Section 5 below).

## Stage 6: Post-Approval Actions
After approval:

1. **Supervisor notification**: If use-of-force was documented, the supervising officer is automatically notified.
2. **Case file assembly**: If an arrest was made, all documents, evidence references, and the audit trail are assembled into a case file.
3. **RMS submission**: Reports are formatted for the department's Records Management System (mocked for hackathon).
4. **Incident stored in queryable database**: Feeds the analytics and voice query system.

## Stage 7: Queryable Voice Database
The officer can call the same number at any time and ask:
- "How many use-of-force incidents did we have this quarter?"
- "Pull up the report from the Oak Street domestic last Tuesday"
- "What reports are pending my review?"
- "What's our arrest count this month?"

The agent queries DynamoDB, computes analytics, and responds by voice. For complex results, it also sends a follow-up SMS.

## Stage 8: Body Cam Integration (STRETCH GOAL - only if time permits)
After documents are generated from the conversation, the officer can optionally upload body cam audio. The agent transcribes it and cross-references against the officer's account:
- Additions: details captured on body cam that the officer didn't mention
- Discrepancies: differences between officer's account and body cam audio (presented neutrally for the officer to resolve)
- Verifications: body cam audio confirming the officer's account

This is NOT core scope. Only implement if all other phases are complete.

---

# 4. TECHNICAL ARCHITECTURE

## The Voice Pipeline (Real-Time Path)

```
Officer's Phone
    |
    v
Twilio (receives call, opens WebSocket)
    |
    v
Daily WebRTC (audio transport)
    |
    v
Pipecat Pipeline:
    Silero VAD (voice activity detection, background)
    + SmartTurn (ML turn detection, background fallback)
    + DTMF Processor (# key detection, primary turn signal)
    |
    v
Nemotron Speech ASR (speech to text, streaming)
    |
    v
Nemotron 3 Super (LLM - orchestrator brain, via NIM API)
    |
    v
Magpie TTS (text to speech)
    |
    v
Daily WebRTC -> Twilio -> Officer's Phone
```

## The Conversation State Machine (Pipecat Flows)

```
GREETING
  -> Officer provides badge number
  -> Agent looks up officer in roster, confirms identity

OPEN_NARRATIVE
  -> Agent: "Go ahead, tell me what happened. Press # when done."
  -> Officer narrates freely. Agent listens silently, extracts entities.
  -> DTMF # pressed -> transition

REPORT_SUGGESTION
  -> Agent suggests report types based on extracted entities
  -> Officer confirms or modifies
  -> Officer's decision is captured as labeled training data

GAP_FILLING
  -> Agent asks targeted questions one at a time
  -> Officer answers, presses # when done (SmartTurn as fallback)
  -> Repeat until all critical fields are filled

COMPLETION
  -> Agent confirms all information gathered
  -> Triggers parallel document generation
  -> Agent says "Your reports are ready, I sent you a link"

QUERY (alternate entry point)
  -> Officer called to ask a question, not file a report
  -> Agent queries the database and responds
```

Each state dynamically updates the system prompt and available tool functions. In OPEN_NARRATIVE, the agent has no tools (just listens). In GAP_FILLING, the agent can call check_missing_fields() to see what's still needed.

## Sub-Agent Architecture (Hierarchical)

```
Orchestrator (Nemotron 3 Super)
  - Conducts the conversation
  - Extracts entities
  - Determines which reports are needed
  - Dispatches to specialists
        |
        +-- Incident Report Agent (Nemotron 3 Nano) -- runs in parallel
        +-- Arrest Report Agent (Nemotron 3 Nano)   -- runs in parallel
        +-- Use-of-Force Agent (Nemotron 3 Nano)    -- runs in parallel
        +-- Accident Report Agent (Nemotron 3 Nano)  -- runs in parallel
        |
        v
  Consistency Checker
  - Cross-references all generated documents
  - Flags mismatched timestamps, names, facts
```

Why hierarchical (not purely parallel): The conversation MUST be conducted by a single orchestrator because it needs to know what ALL report types require and ask questions accordingly. You cannot have four agents asking questions simultaneously. But document generation IS genuinely parallel because each report draws from the same underlying facts independently.

Why Super for orchestrator, Nano for sub-agents: The orchestrator needs strong reasoning to identify gaps across multiple report templates and ask the right follow-up questions. That is multi-step reasoning. The sub-agents fill templates from structured data, which is a simpler task. This uses the right model for the right job.

## Backend Services

```
AWS DynamoDB
  - Incident records (case state, timeline, involved parties)
  - Officer corrections (diffs, correction categories, embeddings)
  - Officer roster (badge, name, rank, unit, supervisor)
  - Analytics data (incident counts, trends, report metrics)

AWS S3
  - AI draft documents (JSON, permanently preserved)
  - Officer-approved final documents (JSON)
  - JSON diffs between draft and final
  - Conversation transcripts
  - Audio recordings

AWS Lambda + EventBridge
  - Async document generation dispatch
  - Notification delivery (supervisor alerts)
  - Scheduled follow-ups (case status, court dates)

AWS Bedrock Knowledge Bases
  - Report templates per department
  - Force continuum definitions
  - Miranda requirements documentation
  - Common charge descriptions and codes
  - State-specific reporting requirements
```

---

# 5. THE AUTO-IMPROVEMENT LOOP (Three Layers)

## What Generates the Training Signal
Every edit the officer makes to an AI-generated document is a correction. The JSON diff captures exactly what the AI got wrong and what the officer changed it to. Corrections are categorized: entity corrections, narrative rewrites, missing fields added, legal language fixes, routing corrections (agent suggested wrong report types), etc.

This is NOT extra work for the officer. Officers already review and approve reports before submission. We are instrumenting an existing step to capture the diff.

## Analogy (How the Three Layers Relate)

Think of a new employee named Sarah who writes reports:

**Layer 1 is Sarah's notebook.** When her boss corrects "verbally aggressive" to "actively resisting verbal commands," Sarah writes it down. Next time a similar situation comes in, she flips to that note before writing. The very next report benefits from the correction. But the notebook has limited pages (prompt length limit). She can only check 5-6 relevant notes per report.

**Layer 2 is the boss doing a spot-check.** Before any report goes out, the boss reviews it against a checklist. Did Sarah fill all fields? Is the narrative faithful to what was said? The boss also keeps a list of every past mistake. If Sarah changes her approach (starts using notes from her notebook), the boss checks whether old mistakes are creeping back in. Layer 2 does not improve Sarah. It prevents her from getting worse.

**Layer 3 is Sarah actually learning.** After 100 reports, she does not need to check her notebook for common patterns anymore. She just knows that this department uses specific force continuum language. The knowledge is internalized. Her baseline is higher. The notebook now only covers rare edge cases, which means it is shorter (faster to check) and more focused.

The three layers are NOT redundant. They operate on different timescales solving different problems:
- Layer 1: "How do I handle THIS incident better, right now?" (minutes)
- Layer 2: "How do I make sure improvements don't cause new problems?" (every update)
- Layer 3: "How do I stop needing the notebook for common patterns?" (weeks)

## Layer 1: DSPy Few-Shot Retrieval (Immediate Improvement)

**What changes:** The prompt the agent uses for the next similar incident.
**What stays the same:** The model weights. Same Nemotron model.
**Speed:** Immediate. The very next incident benefits.

### Mechanism:
1. Officer corrects "verbally aggressive" to "actively resisting verbal commands" on a use-of-force report.
2. This correction is stored as a labeled DSPy example with the transcript segment embedded as a vector.
3. On the next incident, DSPy's KNNFewShot optimizer finds the most similar past corrections (by transcript similarity) and includes them as few-shot examples in the prompt. Not just one correction, multiple (typically 3-5 most relevant).
4. The model generates its output informed by these corrections.
5. Periodically, DSPy's MIPROv2 optimizer recompiles the prompt configuration, testing different combinations of few-shot examples and instruction phrasings to minimize the gap between agent output and officer-corrected output.

### Cold Start:
For the first incidents before corrections exist, we pre-seed with synthetic corrections covering common patterns (force continuum terminology, Miranda documentation, standard charge descriptions).

### Tools:
- DSPy (dspy-ai package)
- sentence-transformers (for embedding corrections)
- FAISS (for vector similarity search during retrieval)

## Layer 2: Cekura Eval-Driven Regression Testing (Quality Gate)

**What changes:** Nothing about the model or prompt directly.
**What it does:** Prevents regressions. Scores every interaction. Blocks bad updates.

### Five Evaluators:

1. **Report completeness** (deterministic, no LLM): Checks if each required field in the report template is populated. Either "officer name" has a value or it doesn't. Simple structural check.

2. **Extraction accuracy** (LLM judge): Did the agent correctly extract all entities from the conversation? An LLM judge reads the transcript and the agent's extraction, scores precision and recall. For the hackathon, we also have pre-labeled ground truth scenarios as fallback.

3. **Narrative faithfulness** (LLM judge): Is the report narrative factually faithful to the conversation transcript? Does it add anything the officer didn't say? Does it omit anything the officer did say?

4. **Cross-document consistency** (deterministic + LLM judge): Do timestamps, names, and facts match across all generated documents?

5. **Question coverage** (LLM judge): Did the orchestrator agent ask about all necessary gaps during the conversation? If Miranda was never discussed and the arrest report has an empty Miranda field, the orchestrator failed.

### Mechanism:
- Every officer correction becomes a Cekura test case.
- Before any Layer 1 prompt update deploys, the full regression suite runs.
- If any previously-passing test case now fails, the update is blocked.
- LLM judges are tuned over time as officer corrections accumulate as ground truth.

## Layer 3: NVIDIA Data Flywheel (Model Weight Improvement)

**What changes:** The actual model weights via LoRA fine-tuning.
**Speed:** Slow. Runs as a batch job when enough corrections accumulate (every 50-100 corrections in production).

### Mechanism:
1. Corrections accumulate over days/weeks.
2. NeMo Curator cleans and structures the correction data.
3. NeMo Customizer runs LoRA fine-tuning on Nemotron 3 Nano.
4. NeMo Evaluator benchmarks fine-tuned vs. base model on the full Cekura test suite.
5. If fine-tuned model scores higher without regressions, it replaces the base model.
6. Layer 1 few-shot corrections that the model has now internalized are retired. The prompt gets shorter, latency drops.

### For the Hackathon Demo:
We cannot run a full fine-tuning cycle live. But we can:
- Show the architecture diagram
- Show a pre-fine-tuned model (trained on synthetic corrections before the hackathon)
- Compare base vs. fine-tuned scores on the Cekura dashboard

## The Flywheel
Corrections -> better prompts (Layer 1) -> validated by regression tests (Layer 2) -> accumulated into fine-tuning data (Layer 3) -> better base model -> fewer corrections needed -> shorter prompts -> lower latency -> cycle continues.

---

# 6. INFRASTRUCTURE AND LATENCY OPTIMIZATIONS

## The Latency Budget
Human conversation requires 300-500ms response time. Delays beyond 500ms feel unnatural. Our pipeline: VAD (10-50ms) + ASR (100-300ms) + LLM (200ms-1s) + TTS (75-200ms). Without optimization, this is 2-4 seconds. With optimization, sub-1-second is achievable.

## Optimization 1: Streaming Pipeline
Instead of waiting for each stage to complete before starting the next, everything streams. ASR transcribes in chunks. The LLM starts processing before the officer finishes speaking. TTS begins synthesizing audio before the LLM finishes generating the full response. This is the single biggest latency reduction.

## Optimization 2: Speculative Speech Processing
The NVIDIA Nemotron Voice Agent Blueprint supports speculative speech processing. The agent pre-generates candidate responses while the officer is still speaking. If the prediction matches, the response is instant. Built into the Nemotron stack; we enable a flag.

## Optimization 3: TTS Caching
Pre-synthesize common agent phrases (greetings, acknowledgments, common follow-up questions like "Was Miranda given?" or "Any witnesses?"). When the agent needs one of these, it plays cached audio instantly (0ms TTS latency) instead of synthesizing in real time.

## Optimization 4: Parallel Pre-Computation
During the conversation, entity extraction, officer lookup, template retrieval, and DSPy few-shot retrieval all run in parallel. By the time the conversation ends, everything is ready for document generation. No cold-start delay.

## Optimization 5: DTMF Turn Detection (Our Custom Optimization)
Using # key press instead of VAD for turn detection eliminates the pause-threshold delay entirely. Standard VAD waits 600ms+ of silence before concluding the speaker is done. DTMF is instant (0ms). This is our novel contribution to the latency budget, specifically designed for police officers who already use push-to-talk radio protocols.

## Optimization 6: Adaptive Turn Detection
Different conversation phases use different turn detection strategies. During open narrative (long, pausing speech), DTMF only. During Q&A (short answers), DTMF primary + SmartTurn fallback. This is a context-adaptive turn detection strategy, defensible as an engineering decision.

## Optimization 7: Nemotron Speech ASR Cache-Aware Architecture
Nemotron Speech ASR processes only new audio deltas instead of re-processing the entire conversation history. This keeps transcription latency stable even for 15-minute conversations. Built into the model; worth calling out to judges.

## GPU and Hosting

### NVIDIA NIM Hosted API (build.nvidia.com)
- Free, OpenAI-compatible, 40 RPM rate limit
- Nemotron 3 Super and Nano are available as hosted endpoints
- ASR and TTS may or may not be available as hosted endpoints (VERIFY BEFORE HACKATHON)
- No GPU needed on our side
- Rate limit risk: 40 RPM might be tight for a real-time voice agent during fast Q&A

### Fallback Models (if NIM doesn't have ASR/TTS)
- STT: Deepgram (150ms latency, native Pipecat integration)
- TTS: Cartesia (low latency) or ElevenLabs
- LLM stays on NVIDIA NIM regardless

### Action Item: Email hackathon organizers to ask about elevated rate limits or GPU access for participants.

---

# 7. KEY DESIGN DECISIONS AND WHY

| Decision | Why |
|----------|-----|
| Active conversation, not ambient listening | Hackathon is about voice agents. The demo needs the agent speaking, asking questions, being interactive. Ambient listening is mostly silent. |
| Law enforcement, not workplace safety | Stronger demo (judges can play the role of officer), larger pain point (3-4 hrs/shift on paperwork), clear competitor to differentiate against (Axon Draft One). |
| DTMF # for turn detection | Noisy hackathon environment, police officer familiarity with push-to-talk, zero latency, demo-proof. |
| Super for orchestrator, Nano for sub-agents | Right model for the right task. Orchestrator needs strong reasoning. Sub-agents need speed. |
| Parallel sub-agents, not sequential | Documents are independent once conversation is complete. Parallel cuts generation time. |
| Report suggestion asks officer for confirmation | Captures labeled training data for the auto-improvement loop. Natural "are we on the same page?" moment. |
| Edit tracking via JSON diff | Same edits serve dual purpose: audit trail (transparency differentiator) AND training data (auto-improvement). |
| DSPy for few-shot optimization | Production-grade framework. KNNFewShot retrieves corrections by similarity. MIPROv2 optimizes prompts with Bayesian moves. |
| Cekura for evaluation | Hackathon sponsor. Native Pipecat integration. Simulation + production monitoring in one platform. |
| Body cam integration is stretch goal | Core value proposition works without it. Only implement if all else is done. |

---

# 8. BUILD ORDER (7-Hour Timeline)

### Hour 0-1: Foundation (HIGHEST RISK)
- Set up project structure, install all dependencies
- Get Twilio webhook + ngrok working
- Get basic Pipecat pipeline running (call the number, hear a greeting, speak, hear a response)
- **If telephony doesn't work by end of hour 1, switch to web-only (Daily WebRTC in browser)**

### Hour 1-2: Conversation Structure
- Implement Pipecat Flows state machine (GREETING -> OPEN_NARRATIVE -> REPORT_SUGGESTION -> GAP_FILLING -> COMPLETION)
- Implement DTMF # detection for turn signaling
- Test: call, narrate, press #, hear agent ask a follow-up

### Hour 2-4: Orchestrator Intelligence + Document Generation
- Write the orchestrator system prompt with full report template awareness
- Implement function calling (check_missing_fields, update_extracted_data)
- Load report templates into knowledge base
- Implement report suggestion + officer confirmation flow
- Implement parallel sub-agent document generation
- Implement consistency checker
- Test: complete a full conversation, see generated documents

### Hour 4-5: Review UI + Edit Tracking
- Build minimal review UI (HTML form displaying generated documents)
- Implement JSON diff computation on approval
- Implement correction storage in DynamoDB
- Test: review documents, make edits, verify diff is captured

### Hour 5-6: Auto-Improvement Loop
- Set up Cekura integration
- Define custom evaluators
- Implement DSPy correction store with FAISS
- Run before/after demo: generate report, make corrections, generate similar report, show improvement
- Set up Cekura dashboard with visible metrics

### Hour 6-7: Polish and Demo Prep
- Run through full demo flow multiple times
- Fix rough edges
- Pre-seed synthetic corrections
- Test in noisy conditions
- Prepare fallback plans

---

# 9. TASKS FOR ARYAN (Before and During Hackathon)

### Before the Hackathon (Tonight)
1. Create accounts: Twilio, NVIDIA (build.nvidia.com), Daily.co, Cekura, AWS
2. Purchase a local Twilio phone number (not toll-free)
3. Go to build.nvidia.com and verify: is Nemotron 3 Super available? Is Nemotron Speech ASR available as hosted API? Is Magpie TTS available?
4. Email hackathon organizers: "Will NVIDIA be providing elevated API rate limits or GPU access for participants?"
5. Install ngrok and test tunneling
6. Gather police report templates (publicly available from many departments):
   - Search "[state] police incident report form PDF"
   - Search "use of force report form template"
   - Search "arrest report form template"
   - Convert into structured JSON: list every field, whether it's required/optional, and what qualifies as a valid value
7. Write 3-5 demo scenarios (realistic incident narratives covering different report types)

### During the Hackathon
1. Test the phone number early and often
2. Gather real-time feedback on law enforcement terminology accuracy
3. Have a specific demo scenario rehearsed and ready
4. Monitor API rate limits

---

# 10. FALLBACK PLANS

| If this fails... | Do this instead... |
|-------------------|--------------------|
| Twilio telephony breaks during demo | Switch to web-based voice (Daily WebRTC in browser). Same pipeline, different transport. |
| NVIDIA NIM rate-limits during demo | Pre-generate report drafts for the demo scenario. Show live pipeline for conversation, pre-generated for documents. |
| ASR/TTS quality is poor | Swap to Deepgram (STT) + Cartesia (TTS). NVIDIA model still handles reasoning. |
| Auto-improvement loop not finished | Show architecture diagram + correction tracking mechanism. Run pre-recorded before/after comparison. |
| Time runs out before all report types | Focus on incident report only. One excellent report type is better than four broken ones. |
| Body cam integration not done | Expected. It is a stretch goal. Do not attempt unless everything else works. |

---

# 11. DEMO STRATEGY (Brief Notes)

The full demo plan will be created once the product is built, but the key demo moments are:

1. **A judge calls the phone number** and plays the role of a police officer describing an incident. The agent asks smart follow-up questions. This is the headline moment.
2. **Documents appear on screen** within 60-90 seconds. Multiple report types, all generated from one conversation.
3. **The judge edits a document.** The diff is captured. We show the Cekura scores.
4. **A second similar scenario runs.** The agent's output is measurably better because of the correction from the first run. Before/after scores visible on the Cekura dashboard.
5. **The transparency/audit trail** is highlighted as a direct answer to the Axon Draft One problem.

---

*This document contains every decision, design choice, and technical detail discussed during planning. If something is not in this document, it was not agreed upon and should be discussed before implementing.*
