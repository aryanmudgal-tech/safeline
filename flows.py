from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


DTMF_END_DIGIT = "#"
COMPLETION_PHRASE = "that's all i have to report"


class ConversationState(StrEnum):
    GREETING = "GREETING"
    OFFICER_ID = "OFFICER_ID"
    OPEN_NARRATIVE = "OPEN_NARRATIVE"
    REPORT_SUGGESTION = "REPORT_SUGGESTION"
    GAP_FILLING = "GAP_FILLING"
    COMPLETION = "COMPLETION"
    GENERATION = "GENERATION"
    DONE = "DONE"
    QUERY = "QUERY"


@dataclass(frozen=True)
class FlowNode:
    state: ConversationState
    prompt: str
    tools: tuple[str, ...]
    next_states: tuple[ConversationState, ...]


def build_flow_nodes() -> dict[ConversationState, FlowNode]:
    return {
        ConversationState.GREETING: FlowNode(
            state=ConversationState.GREETING,
            prompt="Identify as Safeline and ask for the officer badge number.",
            tools=("lookup_officer",),
            next_states=(ConversationState.OFFICER_ID, ConversationState.QUERY),
        ),
        ConversationState.OFFICER_ID: FlowNode(
            state=ConversationState.OFFICER_ID,
            prompt="Validate the officer against the roster and confirm identity.",
            tools=("lookup_officer", "update_extracted_data"),
            next_states=(ConversationState.OPEN_NARRATIVE,),
        ),
        ConversationState.OPEN_NARRATIVE: FlowNode(
            state=ConversationState.OPEN_NARRATIVE,
            prompt="Listen without interruption. Extract entities silently until # is pressed.",
            tools=("update_extracted_data",),
            next_states=(ConversationState.REPORT_SUGGESTION,),
        ),
        ConversationState.REPORT_SUGGESTION: FlowNode(
            state=ConversationState.REPORT_SUGGESTION,
            prompt="Suggest report types based on extracted facts and ask the officer to confirm.",
            tools=("get_report_suggestions", "update_extracted_data"),
            next_states=(ConversationState.GAP_FILLING,),
        ),
        ConversationState.GAP_FILLING: FlowNode(
            state=ConversationState.GAP_FILLING,
            prompt="Ask one prioritized question at a time for missing report fields.",
            tools=("check_missing_fields", "update_extracted_data"),
            next_states=(ConversationState.COMPLETION,),
        ),
        ConversationState.COMPLETION: FlowNode(
            state=ConversationState.COMPLETION,
            prompt="Confirm that enough information has been gathered and begin generation.",
            tools=("trigger_document_generation",),
            next_states=(ConversationState.GENERATION,),
        ),
        ConversationState.GENERATION: FlowNode(
            state=ConversationState.GENERATION,
            prompt="Generate approved reports in parallel and send the review link.",
            tools=("trigger_document_generation",),
            next_states=(ConversationState.DONE,),
        ),
        ConversationState.DONE: FlowNode(
            state=ConversationState.DONE,
            prompt="Provide a short summary and close the call.",
            tools=(),
            next_states=(),
        ),
        ConversationState.QUERY: FlowNode(
            state=ConversationState.QUERY,
            prompt="Answer a database or analytics query for an authenticated officer.",
            tools=("query_incidents",),
            next_states=(ConversationState.DONE,),
        ),
    }


def initial_extraction_state() -> dict:
    return {
        "officer": {},
        "incident": {},
        "subjects": [],
        "force_used": False,
        "force_details": None,
        "miranda_given": None,
        "charges": [],
        "witnesses": [],
        "evidence": [],
        "injuries": [],
        "vehicles": [],
        "approved_report_types": [],
    }

