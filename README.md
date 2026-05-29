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

