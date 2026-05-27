"""
LangGraph OCC (Operations Control Centre) multi-agent graph.

Core flow
---------
  trigger_event
       │
       ▼
  [simulate]   — runs DelayPropagator, builds cascade picture
       │
       ▼
  [analyse]    — Claude synthesises propagation data, calls
                 run_scenario_generation tool, writes OCC briefing
       │
       ▼
  [optimise]   — Claude calls aircraft + crew optimisation tools
                 for scenarios that need resource changes
       │
       ▼
  [brief_occ]  — Claude formats structured approval briefing
       │
       ▼
  [human_gate] — ✋ interrupt() — OCC manager reviews & approves/rejects
       │
       ├─ approved ──► [execute]  — record action, update status
       │
       └─ rejected ──► [abort]    — log rejection, notify stations

Design principles
-----------------
- Agents propose; humans decide.  human_gate is a hard interrupt.
- Claude uses tool_use (not free-form JSON) for all structured outputs.
- System prompt is static per run — not re-sent on every node hop.
- DB path and op_date are passed as state, not hardcoded.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

from argos.agents.state import OCCState
from argos.agents.tools import (
    OCC_TOOLS,
    run_aircraft_optimisation,
    run_crew_optimisation,
    run_propagation,
    run_scenario_generation,
)
from argos.config import get_settings

# ── LLM setup ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are ARGOS, an AI Operations Control Centre (OCC) assistant \
for a Korean Air (KE) Incheon-hub carrier.

Your job is to:
1. Analyse delay propagation data and identify cascade risk
2. Generate exactly 3 recovery scenarios with clear trade-offs
3. Optimise aircraft and crew assignments using the provided tools
4. Prepare a concise, structured briefing for the OCC manager

Domain constraints you must never violate:
- FAR 117 crew duty limits are hard constraints — never recommend exceeding them
- No recovery action may be executed without explicit OCC manager approval
- Aircraft type-compatibility rules must be respected
- ICN is the hub; all rotations are ICN-outbound

Tone: professional, concise, Korean airline OCC style.
Use IATA codes and KE flight number format (KE###).
When citing delays, always use minutes (e.g., "47-min departure delay")."""


def _make_llm(tools: list | None = None) -> ChatAnthropic:
    settings = get_settings()
    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
    )
    if tools:
        return llm.bind_tools(tools)
    return llm


# ── Node: simulate ────────────────────────────────────────────────────────────

def node_simulate(state: OCCState) -> dict:
    """Run delay propagation simulation (no LLM)."""
    result = run_propagation.invoke({
        "db_path":               state["db_path"],
        "op_date":               state["op_date"],
        "trigger_flight_id":     state["trigger_flight_id"],
        "initial_delay_minutes": state["initial_delay_minutes"],
    })
    return {"propagation_summary": result}


# ── Node: analyse ─────────────────────────────────────────────────────────────

def node_analyse(state: OCCState) -> dict:
    """Claude analyses propagation, calls scenario generation tool."""
    prop = state["propagation_summary"]
    prompt = (
        f"A delay has been detected.\n"
        f"Trigger flight: {prop['trigger_flight_id']}\n"
        f"Initial delay: {prop['initial_delay_minutes']} min\n"
        f"Cascade chain: {prop['cascade_chain']}\n"
        f"Cascade depth: {prop['cascade_depth']} flight(s)\n"
        f"Total system delay: {prop['total_delay_minutes']} min\n"
        f"PAX impacted: {prop['total_pax_impacted']}\n\n"
        f"Call run_scenario_generation to produce the 3 recovery scenarios, "
        f"then briefly (3–4 sentences) characterise the disruption severity."
    )
    llm = _make_llm(tools=[run_scenario_generation])
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]
    response: AIMessage = llm.invoke(messages)

    # Execute any tool calls in the response
    scenarios_raw: list[dict] = []
    briefing_parts: list[str] = []

    if response.tool_calls:
        for tc in response.tool_calls:
            if tc["name"] == "run_scenario_generation":
                scenarios_raw = run_scenario_generation.invoke(tc["args"])

    if response.content:
        if isinstance(response.content, str):
            briefing_parts.append(response.content)
        elif isinstance(response.content, list):
            for block in response.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    briefing_parts.append(block["text"])

    return {
        "scenarios_raw": scenarios_raw,
        "scenario_briefing": "\n".join(briefing_parts),
        "messages": [HumanMessage(content=prompt), response],
    }


# ── Node: optimise ────────────────────────────────────────────────────────────

def node_optimise(state: OCCState) -> dict:
    """Claude decides which scenarios need resource optimisation, then runs tools."""
    prop = state["propagation_summary"]
    cascade_chain = prop.get("cascade_chain", [])

    # Always optimise for the full cascade chain
    if len(cascade_chain) <= 1:
        # No downstream impact — skip optimisation
        return {"aircraft_result": None, "crew_result": None}

    disrupted_ids = cascade_chain  # all flights in the cascade

    aircraft_result = run_aircraft_optimisation.invoke({
        "db_path":               state["db_path"],
        "op_date":               state["op_date"],
        "disrupted_flight_ids":  disrupted_ids,
    })
    crew_result = run_crew_optimisation.invoke({
        "db_path":               state["db_path"],
        "op_date":               state["op_date"],
        "disrupted_flight_ids":  disrupted_ids,
    })

    return {
        "aircraft_result": aircraft_result,
        "crew_result":     crew_result,
    }


# ── Node: brief_occ ───────────────────────────────────────────────────────────

def node_brief_occ(state: OCCState) -> dict:
    """Claude writes the final structured OCC approval briefing."""
    prop       = state["propagation_summary"]
    scenarios  = state.get("scenarios_raw", [])
    ac_result  = state.get("aircraft_result")
    cr_result  = state.get("crew_result")

    # Build context block for Claude
    context_lines = [
        "=== OCC DISRUPTION BRIEFING ===",
        f"Trigger  : {prop['trigger_flight_id']}",
        f"Delay    : {prop['initial_delay_minutes']} min",
        f"Cascade  : {prop['cascade_depth']} flight(s), "
        f"{prop['total_pax_impacted']} PAX impacted",
        "",
        "--- RECOVERY SCENARIOS ---",
    ]
    for s in scenarios:
        context_lines += [
            f"[{s['scenario_id']}] {s['name']} (feasibility: {s['feasibility']}, "
            f"cost index: {s['cost_index']:.1f})",
            f"    {s['description']}",
            f"    Action: {s['action_required']}",
            f"    Residual cascade: {s['cascade_depth']} legs, "
            f"{s['total_delay_minutes']} min, {s['total_pax_impacted']} PAX",
            "",
        ]
    if ac_result:
        context_lines += [
            "--- AIRCRAFT RE-ASSIGNMENT ---",
            f"Status: {ac_result['status']}, "
            f"coverage: {ac_result['coverage_rate']:.0%}, "
            f"unassigned: {len(ac_result['unassigned'])}",
            "",
        ]
    if cr_result:
        context_lines += [
            "--- CREW RE-ASSIGNMENT ---",
            f"Status: {cr_result['status']}, "
            f"coverage: {cr_result['coverage_rate']:.0%}, "
            f"FAR 117 violations: {len(cr_result['far117_violations'])}",
        ]
        if cr_result["far117_violations"]:
            for v in cr_result["far117_violations"]:
                context_lines.append(f"  [!] {v}")

    context = "\n".join(context_lines)

    prompt = (
        f"{context}\n\n"
        "Write a concise OCC manager approval briefing (max 250 words). "
        "Structure it as:\n"
        "1. SITUATION: one-sentence summary\n"
        "2. OPTIONS: recommendation + key trade-offs for each scenario\n"
        "3. RECOMMENDATION: which scenario and why\n"
        "4. REQUIRED ACTION: what the OCC manager must approve\n\n"
        "End with: 'Awaiting OCC manager approval.'"
    )

    llm = _make_llm()
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]
    response: AIMessage = llm.invoke(messages)

    briefing = ""
    if isinstance(response.content, str):
        briefing = response.content
    elif isinstance(response.content, list):
        briefing = " ".join(
            b["text"] for b in response.content
            if isinstance(b, dict) and b.get("type") == "text"
        )

    return {
        "scenario_briefing": briefing,
        "messages": [HumanMessage(content=prompt), response],
    }


# ── Node: human_gate ──────────────────────────────────────────────────────────

def node_human_gate(state: OCCState) -> dict:
    """Human-in-the-loop approval gate.

    Interrupts the graph and waits for the OCC manager to supply:
      {"approved_scenario_id": 1|2|3, "approval_notes": "..."}
    or
      {"approved_scenario_id": None, "approval_notes": "Rejected: ..."}
    """
    approval = interrupt({
        "briefing":    state.get("scenario_briefing", ""),
        "scenarios":   state.get("scenarios_raw", []),
        "cascade":     state.get("propagation_summary", {}),
    })
    return {
        "approved_scenario_id": approval.get("approved_scenario_id"),
        "approval_notes":       approval.get("approval_notes", ""),
    }


# ── Node: execute ─────────────────────────────────────────────────────────────

def node_execute(state: OCCState) -> dict:
    """Record the approved recovery action (simulation — no real ops changes)."""
    sid   = state.get("approved_scenario_id")
    notes = state.get("approval_notes", "")
    scenarios = state.get("scenarios_raw", [])
    selected = next((s for s in scenarios if s["scenario_id"] == sid), None)

    if selected:
        summary = (
            f"✅ APPROVED: Scenario {sid} — {selected['name']}\n"
            f"Action: {selected['action_required']}\n"
            f"Notes: {notes}\n"
            f"Residual impact: {selected['cascade_depth']} legs, "
            f"{selected['total_delay_minutes']} min total delay, "
            f"{selected['total_pax_impacted']} PAX affected.\n"
            f"[Simulation] Recovery action logged. Awaiting crew/gate notification."
        )
    else:
        summary = f"✅ APPROVED with notes: {notes}"

    return {"execution_summary": summary}


# ── Node: abort ───────────────────────────────────────────────────────────────

def node_abort(state: OCCState) -> dict:
    """Record rejection and close the disruption event."""
    notes   = state.get("approval_notes", "No reason given")
    summary = (
        f"❌ REJECTED by OCC manager.\n"
        f"Notes: {notes}\n"
        "No recovery action taken. Disruption event closed. "
        "Upstream stations notified to hold."
    )
    return {"execution_summary": summary}


# ── Routing ───────────────────────────────────────────────────────────────────

def route_after_approval(state: OCCState) -> str:
    if state.get("approved_scenario_id") is not None:
        return "execute"
    return "abort"


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_occ_graph(checkpointer=None) -> StateGraph:
    """Build and compile the OCC LangGraph StateGraph."""
    builder = StateGraph(OCCState)

    builder.add_node("simulate",   node_simulate)
    builder.add_node("analyse",    node_analyse)
    builder.add_node("optimise",   node_optimise)
    builder.add_node("brief_occ",  node_brief_occ)
    builder.add_node("human_gate", node_human_gate)
    builder.add_node("execute",    node_execute)
    builder.add_node("abort",      node_abort)

    builder.set_entry_point("simulate")
    builder.add_edge("simulate",  "analyse")
    builder.add_edge("analyse",   "optimise")
    builder.add_edge("optimise",  "brief_occ")
    builder.add_edge("brief_occ", "human_gate")
    builder.add_conditional_edges(
        "human_gate",
        route_after_approval,
        {"execute": "execute", "abort": "abort"},
    )
    builder.add_edge("execute", END)
    builder.add_edge("abort",   END)

    cp = checkpointer or MemorySaver()
    return builder.compile(checkpointer=cp, interrupt_before=["human_gate"])


# ── Public helpers ────────────────────────────────────────────────────────────

def run_until_approval(
    db_path: str,
    op_date: str,
    trigger_flight_id: str,
    initial_delay_minutes: int,
    thread_id: str = "occ-001",
) -> tuple[dict, object]:
    """Run the graph up to the human approval gate.

    Returns (state_at_interrupt, graph) so the caller can inspect the briefing
    and then call resume_after_approval() to continue.
    """
    graph = build_occ_graph()
    config = {"configurable": {"thread_id": thread_id}}
    initial_state: OCCState = {
        "trigger_flight_id":     trigger_flight_id,
        "initial_delay_minutes": initial_delay_minutes,
        "op_date":               op_date,
        "db_path":               db_path,
        "propagation_summary":   {},
        "scenarios_raw":         [],
        "scenario_briefing":     "",
        "aircraft_result":       None,
        "crew_result":           None,
        "approved_scenario_id":  None,
        "approval_notes":        "",
        "execution_summary":     "",
        "messages":              [],
    }
    for chunk in graph.stream(initial_state, config=config, stream_mode="values"):
        last_state = chunk
    return last_state, graph


def resume_after_approval(
    graph: object,
    approved_scenario_id: int | None,
    approval_notes: str = "",
    thread_id: str = "occ-001",
) -> dict:
    """Resume the graph after OCC manager approval or rejection."""
    config = {"configurable": {"thread_id": thread_id}}
    approval_payload = {
        "approved_scenario_id": approved_scenario_id,
        "approval_notes":       approval_notes,
    }
    last_state = None
    for chunk in graph.stream(
        {"type": "interrupt_response", "value": approval_payload},
        config=config,
        stream_mode="values",
    ):
        last_state = chunk
    return last_state or {}
