# Law Enforcement Voice Documentation Agent: Implementation Plan

## Overview
A voice agent that police officers call after incidents. The officer describes what happened in a natural conversation. The agent asks targeted follow-up questions to fill gaps across multiple report types. Once complete, parallel sub-agents generate all required documentation. The officer reviews, edits, and approves. Edits feed a three-layer auto-improvement loop.

---

## Prerequisites and API Keys Required

### Accounts to Create (before hackathon)
1. **Twilio** - Account SID, Auth Token, purchase a local phone number
2. **NVIDIA** - API key from build.nvidia.com for NIM hosted inference
3. **Daily.co** - Developer token from Daily dashboard (for WebRTC transport)
4. **Cekura** - Account + API key from cekura.ai
5. **AWS** - Account with access to DynamoDB, Lambda, S3, SES/SNS
6. **ngrok** - For tunneling local server during development

### Environment Variables (.env)
```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
NVIDIA_API_KEY=
DAILY_API_KEY=
CEKURA_API_KEY=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
```

### Python Packages
```
pipecat-ai[silero,daily,openai,twilio]
pipecat-ai-flows
openai                  # For NVIDIA NIM (OpenAI-compatible API)
twilio
fastapi
uvicorn
boto3                   # AWS SDK
dspy-ai                 # DSPy for few-shot optimization
jsondiffpatch           # Or deepdiff for Python JSON diffing
deepdiff                # Python JSON diff library
sentence-transformers   # For embedding corrections (KNNFewShot)
faiss-cpu               # Vector similarity for correction retrieval
python-dotenv
loguru
aiohttp
websockets
```

---

## Project Structure

```
police-voice-agent/
+-- .env
+-- requirements.txt
+-- README.md
+--
+-- server.py                    # FastAPI server - handles Twilio webhooks + WebSocket
+-- bot.py                       # Main Pipecat pipeline - orchestrator agent
+-- flows.py                     # Pipecat Flows - conversation state machine (Phase 1 / Phase 2)
+--
+-- agents/
|   +-- orchestrator.py          # Orchestrator agent logic + system prompt
|   +-- incident_report.py       # Sub-agent: incident report generation
|   +-- arrest_report.py         # Sub-agent: arrest report generation
|   +-- use_of_force.py          # Sub-agent: use-of-force report generation
|   +-- accident_report.py       # Sub-agent: accident report generation
|   +-- report_router.py         # Determines which reports to generate + asks officer
|   +-- consistency_checker.py   # Merger: cross-document consistency validation
+--
+-- templates/
|   +-- incident_report.json     # Template with required fields for incident report
|   +-- arrest_report.json       # Template with required fields for arrest report
|   +-- use_of_force.json        # Template with required fields for use-of-force report
|   +-- accident_report.json     # Template with required fields for accident report
|   +-- streams.xml              # Twilio TwiML for WebSocket media streams
+--
+-- knowledge_base/
|   +-- report_field_definitions.json   # What each field means + extraction hints
|   +-- force_continuum.json            # Force continuum reference
|   +-- miranda_requirements.json       # Miranda rights documentation requirements
|   +-- charge_descriptions.json        # Common charge descriptions and codes
|   +-- state_requirements/             # State-specific reporting variations
|       +-- california.json
|       +-- new_york.json
|       +-- ...
+--
+-- improvement/
|   +-- dspy_pipeline.py         # DSPy optimization pipeline
|   +-- correction_store.py      # Stores and retrieves officer corrections
|   +-- evaluators.py            # Cekura custom evaluator definitions
+--
+-- storage/
|   +-- dynamodb.py              # DynamoDB operations (incidents, corrections, cases)
|   +-- s3.py                    # S3 operations (documents, transcripts, audio)
+--
+-- review_ui/
|   +-- index.html               # Simple review interface (officer edits documents)
|   +-- api.py                   # FastAPI routes for review UI
+--
+-- mock_data/
|   +-- officer_roster.json      # Mock officer directory
|   +-- demo_scenarios.json      # Pre-built demo scenarios for testing
|   +-- synthetic_corrections.json  # Pre-seeded corrections for DSPy cold start
+--
+-- tests/
    +-- test_extraction.py       # Unit tests for entity extraction
    +-- test_routing.py          # Tests for report type routing
    +-- cekura_scenarios/        # Cekura simulation scenarios
        +-- domestic_disturbance.json
        +-- traffic_stop_arrest.json
        +-- use_of_force.json
```

---

## Implementation Phases

### PHASE 1: Telephony + Voice Pipeline (Foundation)
**Goal**: Officer calls a number, hears the agent speak, agent hears the officer.

#### Step 1.1: Twilio Phone Number + Webhook

Purchase a local Twilio number. Configure it to send incoming calls to your server via webhook.

**server.py** - FastAPI server that:
1. Receives Twilio webhook POST when a call comes in
2. Returns TwiML instructing Twilio to open a WebSocket Media Stream to our server
3. Handles the WebSocket connection and pipes audio to Pipecat

The TwiML template (templates/streams.xml):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="wss://<YOUR_SERVER_URL>/ws/twilio">
      <Parameter name="caller" value="{{From}}" />
    </Stream>
  </Connect>
</Response>
```

Key implementation details from Pipecat docs:
- Use `TwilioWebSocketTransport` from `pipecat.transports.services.twilio`
- Twilio sends audio as mulaw 8kHz, Pipecat handles codec conversion
- DTMF events arrive as separate WebSocket messages with `event: "dtmf"` and `digit: "#"`
- The server needs both HTTP (webhook) and WebSocket (media stream) endpoints

**DTMF Handling**: Twilio Media Streams forward DTMF digits via WebSocket messages. Parse these in the transport layer and emit custom Pipecat frames (e.g., `DTMFFrame`) that the pipeline can react to.

#### Step 1.2: Pipecat Pipeline Setup

**bot.py** - Sets up the core Pipecat pipeline:

```
Pipeline:
  TwilioWebSocketTransport (audio in/out)
  -> SileroVADAnalyzer (voice activity detection, runs in background)
  -> SmartTurn (turn detection, runs in parallel with ASR)
  -> NVIDIA NIM STT (Nemotron Speech ASR via NIM API)
  -> LLM (Nemotron 3 Super via NIM API, OpenAI-compatible)
  -> NVIDIA NIM TTS (Magpie TTS via NIM API)
  -> TwilioWebSocketTransport (audio out)
```

For NVIDIA NIM integration, use the OpenAI-compatible interface:
```python
from pipecat.services.openai import OpenAILLMService

llm_service = OpenAILLMService(
    api_key=os.getenv("NVIDIA_API_KEY"),
    base_url="https://integrate.api.nvidia.com/v1",
    model="nvidia/nemotron-3-super-120b"
)
```

For ASR (Nemotron Speech), check if NIM provides a streaming ASR endpoint. If not available via hosted API, use Deepgram as fallback STT (Pipecat has native Deepgram integration) and document the plan to swap to Nemotron ASR with GPU access.

For TTS (Magpie), same approach: check NIM availability, use Cartesia or ElevenLabs as fallback.

**Critical note**: The NVIDIA NIM hosted API may have limited ASR/TTS model availability compared to LLM. Verify at build.nvidia.com which Nemotron Speech and Magpie endpoints exist. If only the LLM is hosted, use:
- STT: Deepgram (150ms latency, native Pipecat integration)
- LLM: Nemotron 3 Super via NIM
- TTS: Cartesia (low latency) or ElevenLabs

This is still a valid architecture. The NVIDIA model handles the reasoning (the hardest part). ASR and TTS are commodity components.

#### Step 1.3: Basic Conversation Test

At this point, test: call the Twilio number, hear the agent greet you, speak to it, hear a response. This validates the entire audio pipeline end to end before adding any business logic.

---

### PHASE 2: Conversation State Machine (Pipecat Flows)
**Goal**: Structure the conversation into Phase 1 (open narrative) and Phase 2 (targeted Q&A) with DTMF turn detection.

#### Step 2.1: Define Conversation Flow States

Using Pipecat Flows, define the conversation as a state machine:

```
States:
  1. GREETING          -> Agent identifies itself, asks officer badge number
  2. OFFICER_ID        -> Validates officer against roster, confirms identity
  3. OPEN_NARRATIVE    -> Agent says "Go ahead, tell me what happened. Press # when done."
                          Agent listens. No interruption. DTMF # triggers transition.
  4. REPORT_SUGGESTION -> Agent suggests which reports to generate based on narrative.
                          Officer confirms or modifies. (This is a label data capture point.)
  5. GAP_FILLING       -> Agent asks targeted questions for missing fields.
                          DTMF # after each answer, SmartTurn as fallback.
  6. COMPLETION        -> Agent confirms all info gathered, begins document generation.
  7. GENERATION        -> Agent says "Generating your reports, I will send you a link."
                          Sub-agents run in parallel.
  8. DONE              -> Agent provides summary, hangs up or waits for queries.
```

Each state has:
- A system prompt (what the agent should do in this state)
- Available functions/tools (what the agent CAN do)
- Transition conditions (what triggers moving to the next state)

Key Pipecat Flows concept: each node dynamically updates the system prompt and available functions. In OPEN_NARRATIVE state, the agent has no tools (just listens). In GAP_FILLING state, the agent has access to the report templates and can call functions to check field completeness.

#### Step 2.2: DTMF Integration with Flow Transitions

Create a custom Pipecat processor that:
1. Listens for DTMF events from the Twilio WebSocket transport
2. When # is detected during OPEN_NARRATIVE, emits a frame that triggers the flow transition to REPORT_SUGGESTION
3. When # is detected during GAP_FILLING, signals end-of-answer so the agent can process and ask the next question
4. When the hardcoded phrase "that's all I have to report" is detected in the ASR transcript, triggers transition to COMPLETION regardless of current state

Implementation pattern:
```python
class DTMFProcessor(FrameProcessor):
    async def process_frame(self, frame):
        if isinstance(frame, DTMFFrame) and frame.digit == "#":
            if self.current_state == "OPEN_NARRATIVE":
                await self.push_frame(FlowTransitionFrame("REPORT_SUGGESTION"))
            elif self.current_state == "GAP_FILLING":
                await self.push_frame(EndOfAnswerFrame())
```

#### Step 2.3: Smart Fallback Turn Detection

Configure SmartTurn to run in parallel:
- During OPEN_NARRATIVE: SmartTurn is disabled (DTMF only)
- During GAP_FILLING: SmartTurn runs as fallback. If 5 seconds of silence after SmartTurn detects end-of-turn AND no # press, auto-advance.

---

### PHASE 3: Orchestrator Agent (The Brain)
**Goal**: The agent asks intelligent, directed follow-up questions based on what's missing across all report types.

#### Step 3.1: System Prompt Engineering

The orchestrator's system prompt is the most critical piece. It must encode:

1. **Role definition**: You are a police documentation assistant. You help officers create accurate, complete incident reports through natural conversation.

2. **Conversation phase instructions**: 
   - During OPEN_NARRATIVE: Listen. Do not interrupt. Extract entities silently.
   - During REPORT_SUGGESTION: Based on what was described, suggest which reports to generate. Ask officer to confirm.
   - During GAP_FILLING: Ask ONE question at a time. Prioritize legally critical fields first (Miranda, force justification, charges). Ask only about information NOT already provided in the narrative.

3. **Entity extraction schema**: Define what entities to extract from the narrative (names, times, locations, actions, charges, weapons, injuries, witnesses, evidence, vehicles).

4. **Report awareness**: The prompt should reference the report templates so the model knows what fields need to be filled. Instead of dumping all templates into the prompt (which would be massive), use function calling: the agent calls a `check_missing_fields(report_type)` function that returns which fields are still empty.

5. **Tone and behavior**: Professional but conversational. Brief acknowledgments between questions. Never judgmental about the officer's actions. Factual and precise in language.

#### Step 3.2: Function Calling / Tool Use

The orchestrator has these tools available:

```python
tools = [
    {
        "name": "lookup_officer",
        "description": "Look up officer details by badge number from the roster",
        "parameters": {"badge_number": "string"}
    },
    {
        "name": "check_missing_fields",
        "description": "Check which required fields are still missing for a given report type",
        "parameters": {"report_type": "string"}  # incident, arrest, use_of_force, accident
    },
    {
        "name": "update_extracted_data",
        "description": "Update the extracted data store with new information from the conversation",
        "parameters": {"field": "string", "value": "string", "source": "string"}
    },
    {
        "name": "get_report_suggestions",
        "description": "Based on extracted entities, suggest which report types are needed",
        "parameters": {}
    },
    {
        "name": "trigger_document_generation",
        "description": "Trigger parallel document generation for approved report types",
        "parameters": {"report_types": "array of strings"}
    }
]
```

#### Step 3.3: Real-Time Entity Extraction

During the conversation, the orchestrator maintains a running extraction state:

```json
{
    "officer": {"badge": "4521", "name": "Officer Martinez", "unit": "Patrol"},
    "incident": {
        "date": "2026-05-30",
        "time": "02:15",
        "location": "142 Oak Street",
        "type": "domestic_disturbance",
        "narrative_raw": "I responded to a domestic disturbance call at 142 Oak Street..."
    },
    "subjects": [
        {"role": "suspect", "description": "male, approx 30", "name": null, "arrested": true},
        {"role": "victim", "description": "female, standing in doorway", "name": null}
    ],
    "force_used": true,
    "force_details": null,
    "miranda_given": null,
    "charges": null,
    "witnesses": [],
    "evidence": [],
    "injuries": []
}
```

This state is updated incrementally during OPEN_NARRATIVE (the model extracts as it listens) and explicitly during GAP_FILLING (each answer fills specific fields).

#### Step 3.4: RAG with Report Templates

Store report templates in a structured knowledge base (can be local JSON files for hackathon, or AWS Bedrock Knowledge Bases for production).

Each template defines:
- Required fields (must be filled for a valid report)
- Optional fields (good to have but not mandatory)
- Field descriptions (what qualifies as a valid value)
- Extraction hints (what the officer might say to indicate this field)
- Legal requirements (e.g., "Miranda must be documented with specific time if arrest occurred")

The `check_missing_fields` function compares the current extraction state against the template and returns a prioritized list of gaps.

Priority ordering for questions:
1. Legally critical (Miranda, force justification, charges)
2. Identity (suspect name, victim name, witness contacts)
3. Timeline (exact times, sequence of events)
4. Evidence and scene details
5. Administrative (case number assignment, responding units)

---

### PHASE 4: Report Suggestion and Officer Confirmation
**Goal**: Agent suggests which reports to generate, officer confirms. This interaction is captured as labeled data.

After OPEN_NARRATIVE ends, the orchestrator analyzes extracted entities:
- Arrest mentioned? -> Suggest arrest report
- Force used? -> Suggest use-of-force report
- Vehicle accident? -> Suggest accident report
- Always: Incident report (base document for everything)

The agent says: "Based on what you described, I recommend generating an incident report and an arrest report. I also noticed you mentioned using force to restrain the suspect, so a use-of-force report would be needed as well. Should I generate all three, or would you like to adjust?"

Officer confirms or modifies. This confirmation is stored as labeled data:
```json
{
    "extracted_indicators": ["arrest", "force_used", "domestic_disturbance"],
    "agent_suggestion": ["incident_report", "arrest_report", "use_of_force"],
    "officer_decision": ["incident_report", "arrest_report", "use_of_force"],
    "match": true
}
```

Over time, DSPy optimizes the suggestion logic based on accumulated officer decisions.

---

### PHASE 5: Parallel Sub-Agent Document Generation
**Goal**: Generate all approved report types simultaneously from the conversation transcript.

#### Step 5.1: Sub-Agent Architecture

Each sub-agent is a separate LLM call (can use Nemotron 3 Nano for efficiency) that receives:
- The full conversation transcript
- The structured entity extraction
- The specific report template for its document type
- Relevant DSPy few-shot examples (past corrections for this report type)

Sub-agents run in parallel using Python's asyncio:

```python
async def generate_all_reports(report_types, transcript, extraction, corrections):
    tasks = []
    for report_type in report_types:
        template = load_template(report_type)
        few_shots = get_relevant_corrections(report_type, transcript)
        tasks.append(generate_single_report(report_type, template, transcript, extraction, few_shots))
    
    results = await asyncio.gather(*tasks)
    return results
```

Each sub-agent produces a structured JSON document matching its template, with every field populated (or explicitly marked as "not_available" with a reason).

#### Step 5.2: Consistency Checker

After all sub-agents complete, a consistency checker (can be a single LLM call) cross-references the generated documents:
- Do timestamps match across all documents?
- Do names, descriptions, and identifiers match?
- If force is documented in the use-of-force report, is it also mentioned in the incident narrative?
- Are the charges in the arrest report consistent with the incident described?

Any inconsistencies are flagged and auto-corrected where possible, or flagged for officer review.

#### Step 5.3: Notify the Officer

Once documents are generated:
1. Store all drafts in S3 (JSON format)
2. Create an incident record in DynamoDB
3. Send SMS via Twilio to the officer: "Your reports are ready for review: [link to review UI]"
4. If still on the call, the agent says: "Your incident report, arrest report, and use-of-force documentation are ready. I have sent you a link to review them. Is there anything else?"

---

### PHASE 6: Officer Review Interface
**Goal**: A simple web UI where the officer reviews and edits generated documents.

#### Step 6.1: Review UI (Minimal for Hackathon)

A single-page web app (can be plain HTML + JS, or a simple React app) that:
1. Loads the generated documents from the API
2. Displays each report as an editable form (field-by-field, not a raw text block)
3. Shows the conversation transcript alongside, with linked evidence (click a field to see the transcript moment that supports it)
4. Has an "Approve" button per document
5. Has an AI transparency badge: "Draft generated by AI from officer verbal account. Reviewed and approved by [Officer Name, Badge #] on [date/time]."

The review UI is served by the same FastAPI server (review_ui/api.py adds routes for fetching and updating documents).

#### Step 6.2: Edit Tracking

When the officer clicks "Approve":

1. Compute JSON diff between the original AI draft and the officer's edited version using `deepdiff`:

```python
from deepdiff import DeepDiff

diff = DeepDiff(original_draft, officer_version, ignore_order=True)
```

2. Categorize each change:
   - entity_correction (changed a name, time, location)
   - narrative_rewrite (rephrased narrative text)
   - missing_field_added (officer added data the agent missed)
   - incorrect_field_removed (agent hallucinated something not in conversation)
   - routing_correction (officer deleted a report type or added one)
   - legal_language_fix (force continuum terminology, charge descriptions)

3. Store the correction record in DynamoDB:
```json
{
    "incident_id": "INC-2026-0001",
    "report_type": "use_of_force",
    "original_draft": {...},
    "officer_version": {...},
    "diff": {...},
    "correction_categories": ["entity_correction", "legal_language_fix"],
    "transcript_embedding": [0.23, -0.15, ...],
    "timestamp": "2026-05-30T15:30:00Z"
}
```

4. Store both the original and final versions in S3 for permanent audit trail.

---

### PHASE 7: Auto-Improvement Loop
**Goal**: Officer corrections make the agent better over time.

#### Step 7.1: DSPy Setup (Layer 1)

```python
import dspy

# Configure DSPy to use NVIDIA NIM
lm = dspy.LM(
    model="nvidia/nemotron-3-super-120b",
    api_base="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)
dspy.configure(lm=lm)

# Define the extraction signature
class ExtractEntities(dspy.Signature):
    """Extract structured entities from a police officer's incident narrative."""
    transcript = dspy.InputField(desc="The conversation transcript")
    report_type = dspy.InputField(desc="The type of report being generated")
    entities = dspy.OutputField(desc="Structured JSON of extracted entities")

# Define the report generation signature
class GenerateReport(dspy.Signature):
    """Generate a police report from extracted entities and conversation transcript."""
    transcript = dspy.InputField()
    entities = dspy.InputField()
    template = dspy.InputField(desc="The report template with required fields")
    report = dspy.OutputField(desc="Completed report as structured JSON")
```

For correction retrieval, implement KNNFewShot:

```python
from sentence_transformers import SentenceTransformer
import faiss

# Embed corrections
model = SentenceTransformer('all-MiniLM-L6-v2')

class CorrectionStore:
    def __init__(self):
        self.index = faiss.IndexFlatIP(384)  # Inner product for cosine similarity
        self.corrections = []
    
    def add_correction(self, transcript, original, corrected, category):
        embedding = model.encode(transcript)
        faiss.normalize_L2(embedding.reshape(1, -1))
        self.index.add(embedding.reshape(1, -1))
        self.corrections.append({
            "transcript": transcript,
            "original": original,
            "corrected": corrected,
            "category": category
        })
    
    def get_similar_corrections(self, transcript, k=5):
        embedding = model.encode(transcript)
        faiss.normalize_L2(embedding.reshape(1, -1))
        scores, indices = self.index.search(embedding.reshape(1, -1), k)
        return [self.corrections[i] for i in indices[0] if i < len(self.corrections)]
```

#### Step 7.2: Cekura Integration (Layer 2)

Based on Cekura's Pipecat integration:

1. **Setup**: Install Cekura SDK, configure with API key
2. **Define custom metrics** in Cekura dashboard:
   - `report_completeness`: Percentage of required fields filled (deterministic)
   - `extraction_accuracy`: LLM judge comparing extraction vs transcript
   - `narrative_faithfulness`: LLM judge checking report narrative vs transcript
   - `cross_document_consistency`: Deterministic + LLM judge for fact matching
   - `question_coverage`: LLM judge evaluating if agent asked about all gaps

3. **Create simulation scenarios** for regression testing:
   - Domestic disturbance with arrest and force
   - Traffic stop with DUI arrest
   - Simple theft report (incident only)
   - Multi-officer use of force

4. **Connect to Pipecat pipeline**: Cekura captures transcripts, tool calls, and metadata from every conversation.

```python
# In Cekura dashboard or via API:
# 1. Create an agent profile
# 2. Configure Pipecat as the connection method (WebRTC or telephony)
# 3. Define scenarios with persona descriptions
# 4. Define metrics with evaluation prompts
# 5. Run simulations and collect baseline scores
```

5. **Regression testing**: Before any prompt update (from DSPy MIPROv2), run the full scenario suite in Cekura. If any scenario's scores drop, block the update.

#### Step 7.3: NVIDIA Fine-Tuning Pipeline (Layer 3 - Architecture Only for Hackathon)

For the hackathon demo, describe the pipeline and show a pre-fine-tuned model comparison:

1. Accumulated corrections are exported from DynamoDB
2. NeMo Curator filters and structures the data
3. NeMo Customizer runs LoRA fine-tuning on Nemotron 3 Nano
4. NeMo Evaluator benchmarks fine-tuned vs base model on Cekura test suite
5. If fine-tuned model scores higher, promote to production

For the demo: pre-train a fine-tuned model on synthetic correction data before the hackathon. Show base vs fine-tuned scores on the Cekura dashboard.

---

### PHASE 8: Post-Approval Actions
**Goal**: Once reports are approved, trigger downstream actions.

#### Step 8.1: Notification Engine

After officer approves documents:

```python
async def post_approval_actions(incident, approved_reports):
    # 1. Notify supervisor if use-of-force
    if "use_of_force" in approved_reports:
        await send_notification(
            recipient=incident.officer.supervisor,
            type="use_of_force_filed",
            incident_id=incident.id
        )
    
    # 2. Notify supervisor if arrest
    if "arrest_report" in approved_reports:
        await send_notification(
            recipient=incident.officer.supervisor,
            type="arrest_filed",
            incident_id=incident.id
        )
    
    # 3. Create case file if arrest
    if "arrest_report" in approved_reports:
        await create_case_file(incident)
    
    # 4. Submit to RMS (mock for hackathon)
    await submit_to_rms(incident, approved_reports)
    
    # 5. Store in queryable database
    await store_incident_for_analytics(incident)
```

Use AWS Lambda + EventBridge for scheduled follow-ups (corrective actions tracking from safety agent model, adapted: follow-up on case status, court dates, etc.).

#### Step 8.2: Queryable Voice Database

The officer can call the same number and ask:
- "How many use-of-force incidents did we have this quarter?"
- "Pull up the report from the Oak Street domestic last Tuesday"
- "What reports are pending my review?"

Implementation: Add a flow state at the beginning that detects intent:
- If the officer says "I need to file a report" -> go to OPEN_NARRATIVE flow
- If the officer says "I have a question" or asks a data query -> go to QUERY flow

The QUERY flow:
1. Parse the question
2. Query DynamoDB (using LLM function calling to construct the query)
3. Compute analytics if needed (count, average, rate calculations)
4. Respond via voice
5. Offer to send detailed results via SMS/email

---

## Tasks for Aryan (Manual Preparation)

### Before the Hackathon
1. **Create all accounts** (Twilio, NVIDIA, Daily, Cekura, AWS)
2. **Purchase Twilio phone number** (local number, not toll-free)
3. **Verify NVIDIA NIM model availability**: Go to build.nvidia.com, check which models are available (Nemotron 3 Super for LLM, Nemotron Speech for ASR, Magpie for TTS). If ASR/TTS aren't available as hosted endpoints, plan for Deepgram STT + Cartesia/ElevenLabs TTS as fallbacks.
4. **Email hackathon organizers**: Ask about GPU access and any elevated API rate limits for participants.
5. **Gather report templates**: Search for actual police incident report forms, arrest report forms, use-of-force report forms. These are public documents available from many police departments. Convert them into structured JSON templates listing all fields. Key sources:
   - Search "[state] police incident report form PDF"
   - Search "NIBRS incident report template"
   - Search "use of force report form template"
   - The Bureau of Justice Statistics has standardized templates
6. **Create 3-5 demo scenarios**: Write realistic incident narratives that cover different report types (domestic with arrest + force, traffic stop with DUI, simple theft, multi-officer incident). These will be used for Cekura simulations and the live demo.
7. **Set up ngrok**: Install and test ngrok tunneling for Twilio webhook during development.

### During the Hackathon
1. **Gather real-time feedback** from any law enforcement contacts about terminology accuracy
2. **Prepare the demo narrative**: Have a specific incident scenario ready to walk judges through
3. **Test the phone number** early and often - telephony issues are the #1 demo killer

---

## Hackathon Build Order (7-hour timeline)

### Hour 0-1: Foundation
- Set up project structure, install dependencies
- Get Twilio webhook + ngrok working
- Get basic Pipecat pipeline running (call the number, hear a greeting, say something, hear a response)
- This is the riskiest phase - if telephony doesn't work, everything else is blocked

### Hour 1-2: Conversation Structure
- Implement Pipecat Flows state machine (GREETING -> OPEN_NARRATIVE -> REPORT_SUGGESTION -> GAP_FILLING -> COMPLETION)
- Implement DTMF # detection for turn signaling
- Test: call the number, narrate an incident, press #, hear the agent ask a follow-up question

### Hour 2-4: Orchestrator Intelligence
- Write the orchestrator system prompt
- Implement function calling (check_missing_fields, update_extracted_data, etc.)
- Load report templates into the knowledge base
- Implement the report suggestion + officer confirmation flow
- Test: narrate a domestic disturbance with arrest, agent suggests incident + arrest + use-of-force reports, confirm

### Hour 4-5: Document Generation
- Implement parallel sub-agent document generation
- Implement consistency checker
- Build minimal review UI (HTML form displaying generated documents)
- Implement edit tracking (JSON diff)
- Test: complete a full conversation, see generated documents, edit them, verify diff is captured

### Hour 5-6: Auto-Improvement Loop
- Set up Cekura integration (connect to Pipecat pipeline)
- Define custom evaluators in Cekura
- Implement DSPy correction store with FAISS
- Run a before/after demo: generate report, make corrections, generate similar report, show improvement
- Set up the Cekura dashboard with visible metrics

### Hour 6-7: Polish and Demo Prep
- Run through full demo flow multiple times
- Fix any rough edges in conversation flow
- Pre-seed with synthetic corrections for the demo
- Prepare demo talking points
- Test in a noisy environment (simulate hackathon conditions)
- Prepare fallback plans (what if Twilio fails? what if NIM rate-limits?)

---

## Fallback Plans

### If NVIDIA NIM rate-limits hit during demo:
- Pre-generate some report drafts for the most likely demo scenario
- Show the live pipeline for the conversation, switch to pre-generated for document display
- Explain the architecture and show Cekura metrics regardless

### If Twilio telephony fails:
- Fall back to the web-based voice interface (Daily WebRTC directly in browser)
- The voice pipeline is the same, only the transport changes

### If ASR/TTS quality is poor:
- Switch to Deepgram (STT) + Cartesia (TTS) which have proven low-latency
- The NVIDIA model still handles reasoning (the core differentiator)

### If time runs out before auto-improvement is complete:
- Show the architecture diagram and the correction tracking mechanism
- Run a pre-recorded before/after comparison
- The workflow and document generation alone are a strong demo
