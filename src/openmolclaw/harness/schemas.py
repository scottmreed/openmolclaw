"""Router/executor request-response envelopes (OpenMolClaw harness).

The provider-neutral router-first orchestration payloads — intent gating, the
router decision, the step-2 tool-call request, goal-mode policy/status, and the
debug/result envelopes. These carry no billing, plan, or vendor coupling.

Depends only on the standard library + Pydantic.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# --- Goal Mode type aliases -------------------------------------------------

GoalModeLevel = Literal["none", "suggested", "recommended", "required"]
GoalStatusLiteral = Literal["active", "paused", "complete", "blocked", "budget_limited", "cleared"]


# --- Intent gate ------------------------------------------------------------


class IntentType(str, Enum):
    TRIVIAL = "trivial"      # hi, hello, thanks, bye
    UNDO = "undo"            # undo, undo that, revert
    QUESTION = "question"    # how do I, what is, explain
    ACTION = "action"        # create, make, find, show, rotate, etc.


class IntentGateResult(BaseModel):
    """Result from intent gate classification."""
    intent_type: IntentType
    short_circuit: bool = Field(..., description="True if no LLM routing needed")
    direct_response: Optional[str] = Field(None, description="For TRIVIAL intent")
    tool_to_execute: Optional[str] = Field(None, description="For UNDO intent")
    tool_args: Optional[Dict[str, Any]] = Field(None, description="For UNDO intent")
    filtered_tools: Optional[List[Dict[str, Any]]] = Field(None, description="For ACTION intent (how_do_i removed)")
    confidence: float = Field(..., description="Classification confidence")
    multi_action_hint: bool = Field(
        default=False,
        description="Regex detected potential multi-action request (e.g., 'and', 'then')"
    )
    action_count_estimate: int = Field(
        default=1,
        description="Estimated number of distinct actions (from keyword counting)"
    )
    force_tool: Optional[str] = Field(
        default=None,
        description="Tool the router MUST select (Step 2 still runs for arg extraction, unlike tool_to_execute which fully short-circuits)"
    )
    user_notice: Optional[str] = Field(
        default=None,
        description="Deterministic message to prepend to the final reply (not model-generated)"
    )


# --- Debug envelopes --------------------------------------------------------


class ToolCallDebugInfo(BaseModel):
    """Debug information for a tool call."""
    tool_name: str
    input_arguments: Dict[str, Any]
    output_result: Dict[str, Any]
    call_id: Optional[str] = None


class ModelResponseDebugInfo(BaseModel):
    """Debug information for a model response."""
    raw_content: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    model_name: Optional[str] = None
    cost_usd: Optional[float] = None


# --- Step 2 request ---------------------------------------------------------


class Step2ToolCallRequest(BaseModel):
    """Payload for the step2 tool-calling LLM."""

    tool_name: str = Field(..., description="Tool name to force call.")
    tool_args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool.")
    selected_tool_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="Schema to expose to the step2 model."
    )
    skill_slug: Optional[str] = Field(
        default=None,
        description="Skill slug from frontend for skill-specific prompting",
    )
    router_intent: Optional[str] = Field(
        default=None, description="Router intent classification."
    )
    router_context: Optional[str] = Field(
        default=None, description="Router context injected into step2 prompt."
    )
    user_message: Optional[str] = Field(
        default=None, description="Original user message for step2 context."
    )
    canvas_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Full canvas state for canvas_control tool."
    )
    selected_elements: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Selected elements hint for canvas_control tool."
    )
    canvas_alias_mapping: Optional[Dict[str, str]] = Field(
        default=None, description="Alias to element ID mapping for canvas_control tool."
    )
    canvas_snapshot_v2: Optional[Dict[str, Any]] = Field(
        default=None, description="Compact focused/peripheral canvas snapshot for step2 prompt parts."
    )
    lint_feedback: Optional[Dict[str, Any]] = Field(
        default=None, description="Lint feedback from a prior step2 attempt for bounded retry."
    )
    needs_working_memory: bool = Field(
        default=False,
        description="Internal flag from Step1 indicating this request references prior/current state.",
    )
    working_memory_digest: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Compact working-memory payload injected only for state-referenced requests.",
    )


# --- Goal Mode policy / status ----------------------------------------------


class GoalPolicy(BaseModel):
    """Goal Mode complexity assessment emitted by the router.

    The router returns this block alongside its tool decision in a
    single JSON response. No additional LLM call is made for goal detection.
    """

    goal_mode: GoalModeLevel = Field(default="none", description="Goal Mode level: none|suggested|recommended|required.")
    complexity_score: int = Field(default=0, ge=0, le=100, description="0-100 complexity estimate.")
    estimated_steps: int = Field(default=1, ge=1, description="Estimated number of distinct edit steps.")
    max_auto_turns: int = Field(default=1, ge=1, description="Suggested ceiling on automatic continuation turns.")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Router confidence in this assessment.")
    reason: str = Field(default="", description="Short rationale for the goal_mode decision.")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Concrete success conditions for the goal.")
    evidence_required: List[str] = Field(default_factory=list, description="Evidence the harness should check before declaring complete.")
    stop_conditions: List[str] = Field(default_factory=list, description="Conditions under which the loop must stop early.")


class ChatGoalStatus(BaseModel):
    """Live goal status returned with a chat response when a goal is active."""

    goal_id: str = Field(..., description="UUID of the chat_goals row.")
    status: GoalStatusLiteral = Field(..., description="Current goal status.")
    objective: str = Field(..., description="The user-provided objective being pursued.")
    steps_used: int = Field(default=0, ge=0, description="Distinct tool steps consumed by this goal so far.")
    step_cap: int = Field(default=1, ge=1, description="Ceiling on tool steps for this goal.")
    missing: List[str] = Field(default_factory=list, description="Acceptance criteria not yet satisfied.")
    evaluator_reason: Optional[str] = Field(default=None, description="Latest evaluator-emitted reason text.")


# --- Router decision + routing result ---------------------------------------


class RouterDecision(BaseModel):
    """Structured decision returned by the router for step2 execution."""

    intent: str = Field(..., description="Router intent classification.")
    tool_name: str = Field(..., description="Selected tool name for step2.")
    tool_args: Dict[str, Any] = Field(default_factory=dict, description="Prepared tool arguments.")
    conversational: bool = Field(
        default=False,
        description="Whether the router interpreted the request as conversational.",
    )
    disambiguation_required: bool = Field(
        default=False,
        description="Whether target disambiguation is required before execution.",
    )
    disambiguation_reason: Optional[str] = Field(
        default=None, description="Reason for disambiguation requirement."
    )
    selected_tool_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="Tool schema snapshot used for routing."
    )
    confidence: float = Field(0.0, description="Router confidence score.")
    context: Optional[str] = Field(
        default=None, description="Optional router context for downstream prompts."
    )
    needs_working_memory: bool = Field(
        default=False,
        description="Whether Step2 should receive working-memory context for state-referenced requests.",
    )
    goal_policy: Optional[GoalPolicy] = Field(
        default=None,
        description="Goal Mode complexity assessment emitted alongside the tool decision.",
    )
    goal_complete: bool = Field(
        default=False,
        description="True when the router (in a Goal continuation turn) judged the goal complete.",
    )
    goal_complete_reason: Optional[str] = Field(
        default=None, description="Reason text when goal_complete is True."
    )
    goal_evidence_satisfied: List[str] = Field(
        default_factory=list,
        description="Acceptance criteria the router claims are satisfied (validated by harness before honoring).",
    )


@dataclass
class ToolRoutingResult:
    """Result from LLM tool router classifying user intent and extracting parameters."""
    intent_classification: str  # e.g., "molecule_color_change", "multi_step_edit", "conversational"
    tools_to_call: List[str]  # ["execute_molecule_operation"] or [] for conversational
    tool_arguments: Union[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]  # List for multi-action, Dict for single
    execution_mode: str  # "sequential", "parallel", "single", "conversational"
    stop_after_tools: bool  # True to prevent follow-up LLM calls
    user_reply_template: Optional[str]  # "Done. I've {action}." or None for conversational
    system_context: str  # Injected into executor prompt
    confidence: float  # 0.0-1.0, indicates routing confidence
    is_conversational: bool  # True if no tool action needed (chitchat, questions)
    explanation: Optional[str] = None  # Optional explanation/complaint from the model about the routing decision
    usage: Optional[Dict[str, Any]] = None  # Token usage from router call
    cost_usd: float = 0.0  # Cost of router call
    latency_ms: float = 0.0  # Latency of router call
    decision: Optional[RouterDecision] = None  # Router v2 decision payload
    step2_llm_input: Optional[Step2ToolCallRequest] = None  # Prepared step2 request
    selected_tool_schema: Optional[Dict[str, Any]] = None  # Schema for the selected tool
    disambiguation_required: bool = False  # Router asked for disambiguation
    error_type: Optional[str] = None  # Error type if routing failed (e.g., "openrouter_404", "openrouter_data_policy")


__all__ = [
    "GoalModeLevel",
    "GoalStatusLiteral",
    "IntentType",
    "IntentGateResult",
    "ToolCallDebugInfo",
    "ModelResponseDebugInfo",
    "Step2ToolCallRequest",
    "GoalPolicy",
    "ChatGoalStatus",
    "RouterDecision",
    "ToolRoutingResult",
]
