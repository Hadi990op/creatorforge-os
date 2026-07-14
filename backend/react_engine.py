"""
CreatorForge OS — ReAct Agent Engine (v2)
==========================================
Hybrid approach that works with rate-limited LLM providers:

Phase 1: Plan — One LLM call to decide which tools to use and in what order
Phase 2: Execute — Run all tools in parallel/sequence (no LLM needed)
Phase 3: Analyze — One LLM call to analyze tool results and produce final output
Phase 4: Act — Execute any database actions (create invoices, store memory, etc.)

This uses only 2 LLM calls instead of 10+, making it work with free providers.
"""
import json
import asyncio
from typing import Optional
from datetime import datetime

from llm_engine import llm_chat, llm_chat_json, get_active_provider
from agent_tools import execute_tool, get_tools_description, TOOL_DEFINITIONS
from models import db_cursor


def _log_thinking(activity_id: int, agent_name: str, step: int, phase: str, thought: str):
    with db_cursor() as conn:
        conn.execute("""
            INSERT INTO agent_thinking (activity_id, agent_name, step_number, phase, thought)
            VALUES (?, ?, ?, ?, ?)
        """, (activity_id, agent_name, step, phase, thought))


def _log_activity(agent_name: str, action: str, summary: str, entity_type: str = None,
                  entity_id: int = None, details: str = None, status: str = "completed"):
    with db_cursor() as conn:
        conn.execute("""
            INSERT INTO agent_activities (agent_name, action, entity_type, entity_id, summary, details, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (agent_name, action, entity_type, entity_id, summary, details, status))
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _create_approval(entity_type: str, entity_id: int, agent_name: str,
                     title: str, summary: str):
    with db_cursor() as conn:
        cur = conn.execute("""
            INSERT INTO approval_queue (entity_type, entity_id, agent_name, title, summary)
            VALUES (?, ?, ?, ?, ?)
        """, (entity_type, entity_id, agent_name, title, summary))
        return cur.lastrowid


def _get_creator(conn, creator_id: int):
    row = conn.execute("SELECT * FROM creators WHERE id = ?", (creator_id,)).fetchone()
    return dict(row) if row else None


def _get_memory_context(conn, creator_id: int) -> str:
    patterns = conn.execute(
        "SELECT pattern_type, pattern_key, pattern_value, insight FROM memory_patterns WHERE creator_id = ? ORDER BY confidence DESC LIMIT 5",
        (creator_id,)
    ).fetchall()
    if not patterns:
        return "No historical patterns available yet."
    lines = ["HISTORICAL PATTERNS (from Memory Agent):"]
    for p in patterns:
        p = dict(p)
        lines.append(f"- {p['pattern_type']}/{p['pattern_key']}: {p['pattern_value']} — {p['insight']}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  Core Hybrid Agent Loop (2 LLM calls only)
# ═══════════════════════════════════════════════════════════════

async def run_agent(
    agent_name: str,
    system_prompt: str,
    task: str,
    creator_id: int = 1,
    entity_type: str = None,
    entity_id: int = None,
    max_iterations: int = 8,
    extra_context: str = "",
) -> dict:
    """
    Run an agent using a hybrid approach:
    1. PLAN: LLM decides which tools to call (1 LLM call)
    2. EXECUTE: Tools are executed (no LLM needed)
    3. ANALYZE: LLM analyzes results and produces final output (1 LLM call)
    4. ACT: Database actions are executed based on LLM analysis
    
    Total: 2 LLM calls (works with rate-limited free providers)
    """
    activity_id = _log_activity(
        agent_name, "agent_started",
        f"🤖 {agent_name.replace('_', ' ').title()} started autonomous task execution",
        entity_type, entity_id, status="started"
    )
    
    _log_thinking(activity_id, agent_name, 0, "task_received",
                  f"📋 Task: {task[:200]}")
    
    # Gather context
    tools_desc = get_tools_description()
    with db_cursor() as conn:
        creator = _get_creator(conn, creator_id)
        memory_context = _get_memory_context(conn, creator_id)
    
    creator_info = ""
    if creator:
        creator_info = f"""CREATOR PROFILE:
- Name: {creator['name']}
- Handle: @{creator['handle']}
- Niche: {creator.get('niche', 'general')}
- Followers: {creator['followers']:,}
- Bio: {creator.get('bio', 'N/A')}
- Monthly Revenue: ${creator.get('monthly_revenue', 0):,.0f}
"""
    
    # ── PHASE 1: PLAN — LLM decides which tools to call ──
    _log_thinking(activity_id, agent_name, 1, "planning",
                  "🧠 Planning approach: deciding which tools to use for this task...")
    
    plan_prompt = f"""{system_prompt}

{creator_info}

{memory_context}

{extra_context}

{tools_desc}

YOUR TASK:
{task}

INSTRUCTIONS:
You are an autonomous agent. Decide which tools you need to call to complete this task.
List the tools you want to call in order, with their arguments.

Respond with ONLY a JSON array of tool calls. Each tool call is an object with "name" and "arguments" fields.
Do NOT include any other text. Just the JSON array.

Example:
[
  {{"name": "web_search", "arguments": {{"query": "Notion app company"}}}},
  {{"name": "market_rate_research", "arguments": {{"niche": "tech", "followers": 45000, "deal_type": "sponsorship"}}}},
  {{"name": "generate_document", "arguments": {{"doc_type": "proposal", "title": "Counter-offer", "content": "..."}}}}
]

Choose the tools that are most relevant for this task. Be specific with arguments.
ALWAYS include "finish" as the LAST tool call with a summary of what you expect to accomplish.

Tool calls:"""
    
    plan_response, provider = await llm_chat(
        plan_prompt, system=system_prompt,
        max_tokens=2000, temperature=0.3, json_mode=True
    )
    
    if not plan_response:
        _log_thinking(activity_id, agent_name, 1, "error",
                      "❌ LLM unavailable for planning. Using direct tool execution.")
        # Fall back to direct execution without LLM
        return await _fallback_execution(agent_name, task, creator_id, activity_id,
                                         entity_type, entity_id, system_prompt)
    
    # Parse the plan
    tool_calls = _parse_tool_calls(plan_response)
    
    if not tool_calls:
        _log_thinking(activity_id, agent_name, 1, "planning",
                      f"Could not parse tool plan. LLM response: {plan_response[:200]}")
        # Try executing based on the task itself
        tool_calls = _auto_plan(agent_name, task, creator_id)
    
    _log_thinking(activity_id, agent_name, 1, "plan_ready",
                  f"📋 Plan: will call {len(tool_calls)} tools: {', '.join(tc.get('name', '?') for tc in tool_calls[:6])}")
    
    # ── PHASE 2: EXECUTE — Run all tools ──
    tool_results = []
    step = 2
    
    for tc in tool_calls:
        tool_name = tc.get("name", "")
        tool_args = tc.get("arguments", {})
        
        if tool_name == "finish":
            continue
        
        _log_thinking(activity_id, agent_name, step, "tool_call",
                      f"🔧 Calling: {tool_name}({json.dumps(tool_args)[:150]})")
        
        result = await execute_tool(tool_name, tool_args, creator_id)
        tool_results.append({"tool": tool_name, "args": tool_args, "result": result})
        
        result_preview = json.dumps(result, indent=2)[:300]
        _log_thinking(activity_id, agent_name, step, "tool_result",
                      f"📊 {tool_name} result: {result_preview}")
        step += 1
    
    # ── PHASE 3: ANALYZE — LLM analyzes results ──
    _log_thinking(activity_id, agent_name, step, "analyzing",
                  "🧠 Analyzing tool results and producing final output...")
    
    # Build the analysis prompt with all tool results
    results_str = "\n\n".join(
        f"TOOL: {r['tool']}\nARGS: {json.dumps(r['args'])}\nRESULT:\n{json.dumps(r['result'], indent=2)[:2000]}"
        for r in tool_results
    )
    
    analysis_prompt = f"""{system_prompt}

{creator_info}

{memory_context}

YOUR TASK:
{task}

You have already executed the following tools. Analyze the results and produce your final output.

TOOL RESULTS:
{results_str}

Based on the tool results above, provide your final analysis and output.
Respond with a JSON object containing your findings and recommendations.
Include any relevant fields that your task requires (fit_score, recommendation, negotiated_amount, draft, etc.).

Final output (JSON):"""
    
    analysis_response, provider2 = await llm_chat(
        analysis_prompt, system=system_prompt,
        max_tokens=2000, temperature=0.4, json_mode=True
    )
    
    if not analysis_response:
        _log_thinking(activity_id, agent_name, step, "error",
                      "❌ LLM unavailable for analysis. Using raw tool results.")
        final_result = {"summary": "Analysis based on tool results", "result": _summarize_tool_results(tool_results)}
    else:
        parsed = _extract_json(analysis_response)
        if parsed:
            final_result = {"summary": parsed.get("summary", "Task completed"), "result": parsed}
        else:
            final_result = {"summary": analysis_response[:500], "result": {}}
    
    _log_thinking(activity_id, agent_name, step + 1, "result",
                  f"✅ {final_result.get('summary', 'Done')[:300]}")
    
    # ── PHASE 4: ACT — Execute any pending actions from the analysis ──
    # If the LLM included actions in its analysis, execute them
    result_data = final_result.get("result", {})
    
    # Check if we need to create documents, invoices, etc. based on analysis
    if "documents_to_create" in result_data:
        for doc in result_data["documents_to_create"]:
            await execute_tool("generate_document", doc, creator_id)
    
    if "patterns_to_store" in result_data:
        for pattern in result_data["patterns_to_store"]:
            await execute_tool("store_memory", pattern, creator_id)
    
    # Log completion
    _log_activity(
        agent_name, "agent_completed",
        f"✅ {agent_name.replace('_', ' ').title()} completed: {final_result.get('summary', 'Done')[:100]}",
        entity_type, entity_id, status="completed"
    )
    
    return {"agent": agent_name, "activity_id": activity_id, "provider": provider, **final_result}


# ═══════════════════════════════════════════════════════════════
#  Helper Functions
# ═══════════════════════════════════════════════════════════════

def _parse_tool_calls(text: str) -> list:
    """Parse tool calls from LLM response."""
    import re
    
    # Try parsing as JSON array directly
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "tool_calls" in data:
            return data["tool_calls"]
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON array from code blocks
    code_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try finding any JSON array in the text
    json_match = re.search(r'\[.*\]', text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    
    return []


def _extract_json(text: str) -> Optional[dict]:
    """Extract a JSON object from text."""
    import re
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    code_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return None


def _summarize_tool_results(results: list) -> dict:
    """Summarize tool results when LLM is unavailable."""
    summary = {}
    for r in results:
        tool = r["tool"]
        result = r["result"]
        if tool == "web_search":
            summary["search_results"] = result.get("results", [])
        elif tool == "market_rate_research":
            summary["market_rates"] = result.get("estimated_range", {})
        elif tool == "competitor_analysis":
            summary["brand_analysis"] = result.get("analysis", "")
        elif tool == "youtube_search":
            summary["youtube_results"] = result.get("results", [])
        elif tool == "generate_document":
            summary["document_id"] = result.get("doc_id")
    return summary


async def _fallback_execution(agent_name: str, task: str, creator_id: int,
                               activity_id: int, entity_type: str, entity_id: int,
                               system_prompt: str) -> dict:
    """Execute tools without LLM planning — for when LLM is unavailable."""
    tool_calls = _auto_plan(agent_name, task, creator_id)
    
    tool_results = []
    step = 2
    for tc in tool_calls:
        tool_name = tc.get("name", "")
        tool_args = tc.get("arguments", {})
        
        _log_thinking(activity_id, agent_name, step, "tool_call",
                      f"🔧 Calling: {tool_name}({json.dumps(tool_args)[:150]})")
        
        result = await execute_tool(tool_name, tool_args, creator_id)
        tool_results.append({"tool": tool_name, "args": tool_args, "result": result})
        
        _log_thinking(activity_id, agent_name, step, "tool_result",
                      f"📊 {tool_name} result: {json.dumps(result)[:200]}")
        step += 1
    
    _log_thinking(activity_id, agent_name, step, "result",
                  "✅ Tools executed (LLM was unavailable for analysis)")
    
    _log_activity(
        agent_name, "agent_completed",
        f"✅ {agent_name.replace('_', ' ').title()} completed (fallback mode)",
        entity_type, entity_id, status="completed"
    )
    
    return {
        "agent": agent_name,
        "activity_id": activity_id,
        "summary": "Tools executed in fallback mode (LLM unavailable)",
        "result": _summarize_tool_results(tool_results),
        "fallback": True,
    }


def _auto_plan(agent_name: str, task: str, creator_id: int) -> list:
    """Generate a tool plan without LLM — based on agent type and task."""
    import re
    
    if agent_name == "deal_agent":
        # Extract brand name from task
        brand_match = re.search(r'Brand:\s*(.+?)(?:\n|$)', task)
        brand_name = brand_match.group(1).strip() if brand_match else "unknown"
        
        followers_match = re.search(r'Followers:\s*([\d,]+)', task)
        followers = int(followers_match.group(1).replace(",", "")) if followers_match else 50000
        
        niche_match = re.search(r'Niche:\s*(\w+)', task)
        niche = niche_match.group(1) if niche_match else "general"
        
        return [
            {"name": "web_search", "arguments": {"query": brand_name}},
            {"name": "competitor_analysis", "arguments": {"brand_name": brand_name, "creator_niche": niche}},
            {"name": "market_rate_research", "arguments": {"niche": niche, "followers": followers, "deal_type": "sponsorship"}},
            {"name": "db_lookup", "arguments": {"table": "deals"}},
            {"name": "generate_document", "arguments": {
                "doc_type": "proposal",
                "title": f"Counter-offer Proposal - {brand_name}",
                "content": f"Sponsorship counter-offer proposal for {brand_name}."
            }},
            {"name": "finish", "arguments": {"summary": f"Researched {brand_name}, analyzed market rates, generated counter-offer proposal"}}
        ]
    
    elif agent_name == "content_agent":
        niche_match = re.search(r'niche[:\s]+(\w+)', task, re.IGNORECASE)
        niche = niche_match.group(1) if niche_match else "general"
        
        return [
            {"name": "trend_research", "arguments": {"niche": niche, "platform": "all"}},
            {"name": "youtube_search", "arguments": {"query": f"{niche} trending 2025"}},
            {"name": "db_lookup", "arguments": {"table": "content_items"}},
            {"name": "finish", "arguments": {"summary": "Researched trends and YouTube content for the creator's niche"}}
        ]
    
    elif agent_name == "memory_agent":
        return [
            {"name": "db_lookup", "arguments": {"table": "deals"}},
            {"name": "db_lookup", "arguments": {"table": "content_items"}},
            {"name": "db_lookup", "arguments": {"table": "memory_patterns"}},
            {"name": "web_search", "arguments": {"query": "creator economy trends 2025"}},
            {"name": "generate_document", "arguments": {
                "doc_type": "report",
                "title": "Memory Agent Insights Report",
                "content": "Analysis of creator's deals, content, and patterns."
            }},
            {"name": "finish", "arguments": {"summary": "Analyzed all deals and content, stored patterns"}}
        ]
    
    elif agent_name == "finance_agent":
        return [
            {"name": "db_lookup", "arguments": {"table": "invoices"}},
            {"name": "db_lookup", "arguments": {"table": "deals"}},
            {"name": "web_search", "arguments": {"query": "freelance creator tax rates 2025"}},
            {"name": "finish", "arguments": {"summary": "Analyzed invoices and tax information"}}
        ]
    
    return [{"name": "finish", "arguments": {"summary": "No specific plan for this agent type"}}]
