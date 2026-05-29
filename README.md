# Safeline

Safeline is a law-enforcement voice documentation agent for the Cekura + Daily Voice Agents Hackathon. Officers call a Twilio number, narrate an incident, press `#` when done, answer targeted follow-up questions, then review AI-generated reports with a preserved audit trail.

The initial scaffold follows `implementation_plan.md` and `project_briefing.md`: FastAPI + Pipecat for voice, an orchestrator plus specialist report agents, JSON report templates, a lightweight review UI, storage adapters, and the three-layer improvement loop.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn server:app --reload
```

Then configure Twilio to send inbound calls to:

```text
https://<your-ngrok-domain>/twilio/voice
```

## Scaffold Map

```text
server.py                 FastAPI HTTP/WebSocket entry point for Twilio and review UI
bot.py                    Pipecat pipeline configuration placeholder
flows.py                  Conversation states and transition metadata
agents/                   Orchestrator, routing, report agents, consistency checker
templates/                Structured report templates and Twilio TwiML
knowledge_base/           Field definitions, legal references, state requirements
improvement/              Correction retrieval, DSPy hooks, evaluator stubs
storage/                  DynamoDB and S3 adapters
review_ui/                Minimal officer review interface and API routes
mock_data/                Officer roster, demo scenarios, synthetic corrections
tests/                    Basic extraction and routing tests
```

## Build Priorities

1. Wire Twilio Media Streams into the Pipecat transport.
2. Implement Pipecat Flows for `GREETING -> OPEN_NARRATIVE -> REPORT_SUGGESTION -> GAP_FILLING -> COMPLETION`.
3. Connect NVIDIA NIM for the orchestrator LLM and worker report agents.
4. Add Deepgram/Cartesia fallbacks if NVIDIA ASR/TTS hosted endpoints are unavailable.
5. Replace in-memory demo stores with DynamoDB/S3 in the review approval path.

## Phase 1 Telephony Check

The current Phase 1 implementation verifies the phone path before AI services are wired:

```text
Officer phone -> Twilio number -> /twilio/voice -> /ws/twilio
```

Run the app:

```bash
uvicorn server:app --reload
```

Expose it:

```bash
ngrok http 8000
```

Configure the Twilio phone number from the ngrok URL:

```bash
python scripts/configure_twilio_number.py --public-url https://<your-ngrok-domain>
```

Then call the Twilio number. You should hear the initial Safeline greeting, and the app should show call/media/DTMF activity at:

```text
http://127.0.0.1:8000/phase1/status
```
