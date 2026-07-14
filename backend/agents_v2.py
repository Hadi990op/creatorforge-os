"""
CreatorForge OS — Agent Module (v2 — ReAct)
=============================================
Agents now use the ReAct engine — they reason, call tools, see results,
and continue until the task is complete. This is real autonomy, not
just a single LLM call that produces text.

Agent-to-agent communication:
  - When a deal is approved, the Deal Agent triggers the Finance Agent
    (auto-generate invoice) and Content Agent (schedule content)
  - The Memory Agent runs independently to learn from all outcomes
"""
import json
from datetime import datetime
from models import db_cursor
from react_engine import run_agent, _log_activity, _create_approval, _log_thinking
from agent_prompts_v2 import (
    DEAL_AGENT_SYSTEM, DEAL_AGENT_TASK_TEMPLATE,
    CONTENT_AGENT_SYSTEM, CONTENT_AGENT_TASK_TEMPLATE,
    FINANCE_AGENT_SYSTEM, FINANCE_AGENT_TASK_TEMPLATE,
    MEMORY_AGENT_SYSTEM, MEMORY_AGENT_TASK_TEMPLATE,
)
from llm_engine import get_active_provider


def _get_creator_id() -> int:
    """Get the first creator's ID."""
    with db_cursor() as conn:
        row = conn.execute("SELECT id FROM creators ORDER BY id LIMIT 1").fetchone()
        return row[0] if row else 1


# ═══════════════════════════════════════════════════════════════
#  DEAL AGENT — Autonomous Brand Deal Analysis & Negotiation
# ═══════════════════════════════════════════════════════════════

async def deal_agent_analyze(creator_id: int, deal_id: int) -> dict:
    """
    Run the Deal Agent on a deal.
    The agent will:
    1. Research the brand on the web
    2. Research market rates
    3. Analyze brand fit
    4. Generate a counter-offer proposal document
    5. Create an invoice and schedule content if it's a good fit
    6. Save insights to memory
    """
    # Get deal details
    with db_cursor() as conn:
        deal = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
        if not deal:
            return {"error": "Deal not found"}
        deal = dict(deal)

    task = DEAL_AGENT_TASK_TEMPLATE.format(
        brand_name=deal["brand_name"],
        brand_type=deal.get("brand_type", "unknown"),
        deal_type=deal.get("deal_type", "sponsorship"),
        offer_amount=deal.get("offer_amount", 0),
        description=deal.get("description", ""),
    )

    # Run the agent
    result = await run_agent(
        agent_name="deal_agent",
        system_prompt=DEAL_AGENT_SYSTEM,
        task=task,
        creator_id=creator_id,
        entity_type="deal",
        entity_id=deal_id,
        max_iterations=10,
    )

    # Parse the agent's result and update the deal
    agent_result = result.get("result", {})
    analysis = _parse_deal_analysis(agent_result, deal)

    # Update deal in database
    with db_cursor() as conn:
        conn.execute("""
            UPDATE deals SET status = 'analyzed', fit_score = ?, fit_reasoning = ?,
            negotiated_amount = ?, negotiated_terms = ?, agent_analysis = ?,
            updated_at = datetime('now')
            WHERE id = ?
        """, (
            analysis.get("fit_score", 0.5),
            analysis.get("fit_reasoning", "Analysis complete"),
            analysis.get("negotiated_amount", deal.get("offer_amount", 0)),
            analysis.get("negotiated_terms", "Standard terms"),
            result.get("summary", "Deal analyzed by agent"),
            deal_id
        ))

    # Route to approval based on recommendation
    rec = analysis.get("recommendation", "moderate_fit")
    provider = get_active_provider()

    if rec != "off_brand":
        approval_summary = (
            f"**{deal['brand_name']}** — ${analysis.get('negotiated_amount', 0):,.0f}\n"
            f"Fit: {analysis.get('fit_score', 0):.0%} | {rec.replace('_', ' ')}\n"
            f"Price: {analysis.get('price_assessment', 'N/A')}\n\n"
            f"{analysis.get('fit_reasoning', '')}\n\n"
            f"**Counter-offer:** {analysis.get('negotiated_terms', 'N/A')}\n\n"
            f"**Agent research:** {result.get('summary', '')[:200]}"
        )
        approval_id = _create_approval("deal", deal_id, "deal_agent",
                                       f"Deal: {deal['brand_name']}", approval_summary)
        with db_cursor() as conn:
            conn.execute("UPDATE deals SET status = 'negotiating', needs_approval = 1 WHERE id = ?", (deal_id,))

        _log_activity("deal_agent", "routed_for_approval",
                      f"⏳ Deal from {deal['brand_name']} routed for approval — counter-offer: ${analysis.get('negotiated_amount', 0):,.0f}",
                      "deal", deal_id, status="awaiting_approval")
    else:
        with db_cursor() as conn:
            conn.execute("UPDATE deals SET status = 'declined', needs_approval = 0 WHERE id = ?", (deal_id,))
        _log_activity("deal_agent", "auto_declined",
                      f"❌ Deal from {deal['brand_name']} auto-declined (off-brand)",
                      "deal", deal_id, status="completed")

    return {
        "analysis": analysis,
        "agent_summary": result.get("summary", ""),
        "activity_id": result.get("activity_id"),
        "approval_id": approval_id if rec != "off_brand" else None,
        "provider": provider
    }


def _parse_deal_analysis(result: dict, deal: dict) -> dict:
    """Parse the agent's result into a deal analysis."""
    def _safe_float(val, default=0):
        try:
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                return float(val)
            if isinstance(val, dict):
                # Extract a number from dict
                for k in ["min", "value", "amount", "price"]:
                    if k in val:
                        return float(val[k])
                return default
        except (ValueError, TypeError):
            pass
        return default
    
    return {
        "fit_score": _safe_float(result.get("fit_score"), 0.5),
        "fit_reasoning": str(result.get("fit_reasoning", "Analysis complete.")),
        "recommendation": str(result.get("recommendation", "moderate_fit")),
        "price_assessment": str(result.get("price_assessment", "fair market value")),
        "benchmark_price": _safe_float(result.get("benchmark_price"), 0),
        "negotiated_amount": _safe_float(result.get("negotiated_amount"), deal.get("offer_amount", 0)),
        "negotiated_terms": str(result.get("negotiated_terms", "Standard terms.")),
        "agent_analysis": str(result.get("summary", "Deal analyzed.")),
    }


# ═══════════════════════════════════════════════════════════════
#  CONTENT AGENT — Autonomous Content Creator
# ═══════════════════════════════════════════════════════════════

async def content_agent_draft(creator_id: int, content_id: int) -> dict:
    """
    Run the Content Agent on a content item.
    The agent will:
    1. Research trending topics in the creator's niche
    2. Search YouTube for popular content
    3. Write the full, complete content draft
    4. Generate a content strategy document
    5. Save content insights to memory
    """
    with db_cursor() as conn:
        content = conn.execute("SELECT * FROM content_items WHERE id = ?", (content_id,)).fetchone()
        if not content:
            return {"error": "Content not found"}
        content = dict(content)

    task = CONTENT_AGENT_TASK_TEMPLATE.format(
        title=content["title"],
        content_type=content.get("content_type", "post"),
        platform=content.get("platform", "instagram"),
        brief=content.get("brief", ""),
    )

    result = await run_agent(
        agent_name="content_agent",
        system_prompt=CONTENT_AGENT_SYSTEM,
        task=task,
        creator_id=creator_id,
        entity_type="content",
        entity_id=content_id,
        max_iterations=10,
    )

    agent_result = result.get("result", {})
    draft = agent_result.get("draft", result.get("summary", ""))

    # Update content in database
    with db_cursor() as conn:
        conn.execute("""
            UPDATE content_items SET status = 'draft_ready', draft = ?, agent_reasoning = ?,
            updated_at = datetime('now')
            WHERE id = ?
        """, (
            draft,
            agent_result.get("agent_reasoning", result.get("summary", "Content drafted by agent.")),
            content_id
        ))

    # Route to approval
    approval_summary = (
        f"**{content['title']}** — {content.get('platform', 'instagram')}\n"
        f"Content type: {content.get('content_type', 'post')}\n\n"
        f"Draft preview:\n{draft[:500]}...\n\n"
        f"**Agent reasoning:** {agent_result.get('agent_reasoning', '')[:200]}"
    )
    approval_id = _create_approval("content", content_id, "content_agent",
                                   f"Content: {content['title']}", approval_summary)

    return {
        "draft": draft,
        "hashtags": agent_result.get("hashtags", ""),
        "platform_notes": agent_result.get("platform_notes", ""),
        "agent_reasoning": agent_result.get("agent_reasoning", ""),
        "activity_id": result.get("activity_id"),
        "approval_id": approval_id,
    }


# ═══════════════════════════════════════════════════════════════
#  FINANCE AGENT — Autonomous Financial Manager
# ═══════════════════════════════════════════════════════════════

async def finance_agent_invoice(creator_id: int, invoice_id: int) -> dict:
    """Run the Finance Agent on an invoice."""
    with db_cursor() as conn:
        invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not invoice:
            return {"error": "Invoice not found"}
        invoice = dict(invoice)

    # Get deal info if linked
    deal = None
    if invoice.get("deal_id"):
        deal = conn.execute("SELECT * FROM deals WHERE id = ?", (invoice["deal_id"],)).fetchone()
        deal = dict(deal) if deal else None

    task = FINANCE_AGENT_TASK_TEMPLATE.format(
        brand_name=invoice.get("client_name", "Client"),
        amount=invoice.get("amount", 0),
        deal_id=invoice.get("deal_id", 0),
    )

    result = await run_agent(
        agent_name="finance_agent",
        system_prompt=FINANCE_AGENT_SYSTEM,
        task=task,
        creator_id=creator_id,
        entity_type="invoice",
        entity_id=invoice_id,
        max_iterations=8,
    )

    # Update invoice
    with db_cursor() as conn:
        conn.execute("""
            UPDATE invoices SET status = 'pending_approval', agent_notes = ?
            WHERE id = ?
        """, (result.get("summary", "Invoice processed"), invoice_id))

    return {
        "agent_summary": result.get("summary", ""),
        "activity_id": result.get("activity_id"),
    }


# ═══════════════════════════════════════════════════════════════
#  MEMORY AGENT — Autonomous Learning Agent
# ═══════════════════════════════════════════════════════════════

async def memory_agent_learn(creator_id: int) -> dict:
    """Run the Memory Agent to learn patterns from all data."""
    result = await run_agent(
        agent_name="memory_agent",
        system_prompt=MEMORY_AGENT_SYSTEM,
        task=MEMORY_AGENT_TASK_TEMPLATE,
        creator_id=creator_id,
        max_iterations=10,
    )

    return {
        "agent_summary": result.get("summary", ""),
        "patterns_found": result.get("result", {}).get("patterns_found", []),
        "activity_id": result.get("activity_id"),
    }


# ═══════════════════════════════════════════════════════════════
#  APPROVAL RESOLUTION — with agent-to-agent triggers
# ═══════════════════════════════════════════════════════════════

async def resolve_approval(approval_id: int, decision: str) -> dict:
    """
    Resolve an approval and trigger downstream agents.
    
    When a deal is approved:
    - Finance Agent auto-generates an invoice
    - Content Agent auto-schedules content
    
    When content is approved:
    - Status updates to 'approved' (ready to publish)
    """
    with db_cursor() as conn:
        approval = conn.execute("SELECT * FROM approval_queue WHERE id = ?", (approval_id,)).fetchone()
        if not approval:
            return {"error": "Approval not found"}
        approval = dict(approval)

        entity_type = approval["entity_type"]
        entity_id = approval["entity_id"]
        agent_name = approval["agent_name"]

        # Update approval status
        conn.execute("""
            UPDATE approval_queue SET status = ?, resolved_at = datetime('now')
            WHERE id = ?
        """, (decision, approval_id))

        auto_invoice_id = None
        auto_content_id = None

        if entity_type == "deal":
            if decision == "approved":
                conn.execute("""
                    UPDATE deals SET status = 'approved', updated_at = datetime('now')
                    WHERE id = ?
                """, (entity_id,))
                
                # Get the deal for auto-triggering
                deal = conn.execute("SELECT * FROM deals WHERE id = ?", (entity_id,)).fetchone()
                if deal:
                    deal = dict(deal)
                    creator_id = deal["creator_id"]
                    
                    # Auto-generate invoice
                    cur = conn.execute("""
                        INSERT INTO invoices (creator_id, deal_id, client_name, amount, status, agent_notes)
                        VALUES (?, ?, ?, ?, 'draft', 'Auto-generated upon deal approval')
                    """, (creator_id, entity_id, deal["brand_name"],
                          deal.get("negotiated_amount") or deal.get("offer_amount", 0)))
                    auto_invoice_id = cur.lastrowid
                    
                    # Auto-schedule content
                    cur = conn.execute("""
                        INSERT INTO content_items (creator_id, title, content_type, brief, platform, status)
                        VALUES (?, ?, 'post', ?, 'instagram', 'brief')
                    """, (creator_id, f"Sponsored content for {deal['brand_name']}",
                          f"Create sponsored content for {deal['brand_name']} — {deal.get('description', '')}"))
                    auto_content_id = cur.lastrowid
            else:
                conn.execute("""
                    UPDATE deals SET status = 'declined', updated_at = datetime('now')
                    WHERE id = ?
                """, (entity_id,))

        elif entity_type == "content":
            if decision == "approved":
                conn.execute("""
                    UPDATE content_items SET status = 'approved', updated_at = datetime('now')
                    WHERE id = ?
                """, (entity_id,))
            else:
                conn.execute("""
                    UPDATE content_items SET status = 'declined', updated_at = datetime('now')
                    WHERE id = ?
                """, (entity_id,))

        elif entity_type == "invoice":
            if decision == "approved":
                conn.execute("""
                    UPDATE invoices SET status = 'sent', updated_at = datetime('now')
                    WHERE id = ?
                """, (entity_id,))
            else:
                conn.execute("""
                    UPDATE invoices SET status = 'draft', updated_at = datetime('now')
                    WHERE id = ?
                """, (entity_id,))

    # Log the approval
    _log_activity(agent_name, f"approval_{decision}",
                  f"{'✅' if decision == 'approved' else '❌'} Creator {decision} {entity_type} #{entity_id}",
                  entity_type, entity_id, status=decision)

    # Trigger downstream agents asynchronously
    if auto_invoice_id:
        _log_activity("finance_agent", "auto_invoice_created",
                      f"💰 Auto-generated invoice #{auto_invoice_id} for approved deal",
                      "invoice", auto_invoice_id, status="completed")
    
    if auto_content_id:
        _log_activity("content_agent", "auto_content_scheduled",
                      f"✍️ Auto-scheduled content #{auto_content_id} for approved deal",
                      "content", auto_content_id, status="completed")

    return {
        "status": "resolved",
        "decision": decision,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "auto_invoice_id": auto_invoice_id,
        "auto_content_id": auto_content_id,
    }
