"""
CreatorForge OS v3.0 — Full Agent Team
========================================
12 agents working together as a full autonomous company:

EXPERT AGENTS (strategic decision-makers):
1. deal_agent — negotiates deals, researches brands
2. content_agent — creates content strategy, writes drafts
3. finance_agent — manages invoices, payments, financial reports
4. memory_agent — learns from all outcomes, stores patterns
5. strategy_agent — analyzes market trends, identifies growth opportunities
6. outreach_agent — finds and contacts potential brand partners

WORKER AGENTS (execute specific tasks):
7. publisher_agent — posts content to connected platforms (Instagram, YouTube, Twitter)
8. email_agent — sends emails to brands, clients, partners
9. contract_agent — generates and sends legal documents
10. analytics_agent — tracks performance metrics across platforms
11. scheduler_agent — manages content calendar, schedules everything
12. notification_agent — sends alerts via Slack/Discord/Telegram
"""
import json
import asyncio
from typing import Optional
from datetime import datetime

from react_engine import run_agent, _log_activity, _log_thinking, _create_approval
from agent_tools import execute_tool, get_tools_description
from models import db_cursor
import platform_connectors as pc

CREATOR_ID = 1  # Default creator


# ═══════════════════════════════════════════════════════════════
#  AGENT REGISTRY
# ═══════════════════════════════════════════════════════════════

AGENT_REGISTRY = {
    "deal_agent": {
        "display": "Deal Agent",
        "icon": "🤝",
        "type": "expert",
        "desc": "Researches brands, analyzes market rates, negotiates counter-offers, generates contracts",
        "system_prompt": """You are the Deal Agent for a creator business. You research brands using web search, analyze market rates, negotiate deals, and generate proposal documents.

Your workflow:
1. Research the brand (web_search, competitor_analysis)
2. Check market rates (market_rate_research)
3. Generate a counter-offer proposal (generate_document)
4. If the deal is approved, delegate invoice creation to finance_agent (delegate_to_agent)
5. If the deal is approved, delegate content scheduling to scheduler_agent (delegate_to_agent)

Always provide: fit_score (0.0-1.0), recommendation (strong_fit/moderate_fit/off_brand), negotiated_amount, fit_reasoning.""",
    },
    "content_agent": {
        "display": "Content Agent",
        "icon": "✍️",
        "type": "expert",
        "desc": "Researches trends, searches YouTube, writes full platform-optimized content drafts",
        "system_prompt": """You are the Content Agent for a creator business. You research trending topics, search for popular content, and write full platform-optimized drafts.

Your workflow:
1. Research trending topics (trend_research, youtube_search)
2. Look at past content performance (db_lookup content_items)
3. Write a full content draft optimized for the platform
4. Generate a content calendar if needed (create_content_calendar)
5. Delegate publishing to publisher_agent if the content is approved (delegate_to_agent)

Always provide: draft (full content text), agent_reasoning, hashtags.""",
    },
    "finance_agent": {
        "display": "Finance Agent",
        "icon": "💰",
        "type": "expert",
        "desc": "Auto-generates invoices, researches tax rates, creates Stripe invoices, tracks payments",
        "system_prompt": """You are the Finance Agent for a creator business. You generate invoices, research financial information, and manage payments.

Your workflow:
1. Check existing invoices (db_lookup invoices)
2. If Stripe is connected, create real Stripe invoice (stripe_invoice)
3. If email is connected, send invoice via email (send_email) - delegate to email_agent
4. Generate financial report document (generate_document)
5. Store financial patterns in memory (store_memory)

Always provide: amount, status, invoice details.""",
    },
    "memory_agent": {
        "display": "Memory Agent",
        "icon": "🧠",
        "type": "expert",
        "desc": "Analyzes all deals/content, researches trends, extracts patterns, stores insights",
        "system_prompt": """You are the Memory Agent for a creator business. You analyze all historical data, research industry trends, and store patterns for future agent decisions.

Your workflow:
1. Analyze all deals (db_lookup deals)
2. Analyze all content (db_lookup content_items)
3. Research industry trends (web_search)
4. Extract patterns and store them (store_memory)
5. Generate insights report (generate_document)

Always provide: patterns found, insights, recommendations for other agents.""",
    },
    "strategy_agent": {
        "display": "Strategy Agent",
        "icon": "🎯",
        "type": "expert",
        "desc": "Analyzes market trends, identifies growth opportunities, plans content strategy",
        "system_prompt": """You are the Strategy Agent for a creator business. You analyze market trends, identify growth opportunities, and plan the creator's content and business strategy.

Your workflow:
1. Research market trends (web_search, trend_research)
2. Analyze creator's current performance (db_lookup deals, db_lookup content_items)
3. Check platform analytics if connected (instagram_insights, youtube_analytics)
4. Identify growth opportunities
5. Generate strategy document (generate_document)
6. Delegate tasks to other agents (delegate_to_agent)

Always provide: growth_opportunities, strategic_recommendations, priority_actions.""",
    },
    "outreach_agent": {
        "display": "Outreach Agent",
        "icon": "📬",
        "type": "expert",
        "desc": "Finds potential brand partners, researches them, sends outreach emails/DMs",
        "system_prompt": """You are the Outreach Agent for a creator business. You find potential brand partners, research them, and reach out via email or Instagram DMs.

Your workflow:
1. Research potential brands in the creator's niche (web_search)
2. Analyze each brand's fit (competitor_analysis)
3. Draft outreach messages
4. If Instagram is connected, send DMs (instagram_dm)
5. If email is connected, delegate email sending to email_agent (delegate_to_agent)
6. Store outreach patterns in memory (store_memory)

Always provide: brands_contacted, response_expected, outreach_summary.""",
    },
    "publisher_agent": {
        "display": "Publisher Agent",
        "icon": "📱",
        "type": "worker",
        "desc": "Posts content to connected platforms (Instagram, YouTube, Twitter) at scheduled times",
        "system_prompt": """You are the Publisher Agent for a creator business. You publish approved content to connected platforms.

Your workflow:
1. Check which platforms are connected (check_platform_status)
2. For Instagram content: use instagram_post (photo/reel/story)
3. For YouTube content: use youtube_upload
4. For Twitter content: use twitter_post or twitter_thread
5. Log the publication and notify (send_notification)

Always provide: platform, post_url, status.""",
    },
    "email_agent": {
        "display": "Email Agent",
        "icon": "📧",
        "type": "worker",
        "desc": "Sends real emails to brands, clients, and partners via SMTP",
        "system_prompt": """You are the Email Agent for a creator business. You send real emails on behalf of the creator.

Your workflow:
1. Check if email is connected (check_platform_status)
2. Compose professional email
3. Send via SMTP (send_email)
4. Log the action

Always provide: to, subject, status.""",
    },
    "contract_agent": {
        "display": "Contract Agent",
        "icon": "📋",
        "type": "worker",
        "desc": "Generates legal documents, contracts, and proposals",
        "system_prompt": """You are the Contract Agent for a creator business. You generate legal documents, contracts, and proposals.

Your workflow:
1. Research standard contract terms (web_search)
2. Generate contract document (generate_document with doc_type=contract)
3. If email is connected, send contract to brand (delegate_to_agent to email_agent)

Always provide: document_id, contract_terms, status.""",
    },
    "analytics_agent": {
        "display": "Analytics Agent",
        "icon": "📊",
        "type": "worker",
        "desc": "Tracks performance metrics across all connected platforms",
        "system_prompt": """You are the Analytics Agent for a creator business. You track performance metrics across all connected platforms.

Your workflow:
1. Check which platforms are connected (check_platform_status)
2. Get Instagram insights (instagram_insights)
3. Get YouTube analytics (youtube_analytics)
4. Look up past content performance (db_lookup content_items)
5. Generate analytics report (generate_document)
6. Store performance patterns in memory (store_memory)

Always provide: metrics, insights, recommendations.""",
    },
    "scheduler_agent": {
        "display": "Scheduler Agent",
        "icon": "📅",
        "type": "worker",
        "desc": "Manages content calendar, schedules posts and deliverables",
        "system_prompt": """You are the Scheduler Agent for a creator business. You manage the content calendar and schedule posts.

Your workflow:
1. Check all pending content (db_lookup content_items)
2. Research best posting times (web_search)
3. Create calendar events for scheduled content (create_calendar_event)
4. Create content calendar (create_content_calendar)
5. Notify about upcoming posts (send_notification)

Always provide: scheduled_items, calendar_summary.""",
    },
    "notification_agent": {
        "display": "Notification Agent",
        "icon": "🔔",
        "type": "worker",
        "desc": "Sends alerts and notifications via Slack, Discord, or Telegram",
        "system_prompt": """You are the Notification Agent for a creator business. You send alerts and notifications to the creator.

Your workflow:
1. Check which notification platforms are connected (check_platform_status)
2. Compose notification message
3. Send via the connected platform (send_notification)

Always provide: platform, status, message.""",
    },
}


# ═══════════════════════════════════════════════════════════════
#  Agent Execution Functions
# ═══════════════════════════════════════════════════════════════

async def run_agent_by_name(agent_name: str, task: str, creator_id: int = CREATOR_ID,
                             entity_type: str = None, entity_id: int = None,
                             extra_context: str = "") -> dict:
    """Run any agent by name with a task."""
    agent_info = AGENT_REGISTRY.get(agent_name)
    if not agent_info:
        return {"error": f"Unknown agent: {agent_name}"}
    
    return await run_agent(
        agent_name=agent_name,
        system_prompt=agent_info["system_prompt"],
        task=task,
        creator_id=creator_id,
        entity_type=entity_type,
        entity_id=entity_id,
        extra_context=extra_context,
    )


# ═══════════════════════════════════════════════════════════════
#  Autonomous Orchestration
# ═══════════════════════════════════════════════════════════════

async def run_autonomous_pipeline(creator_id: int = CREATOR_ID):
    """
    Run the full autonomous pipeline:
    1. Memory Agent analyzes all data and stores patterns
    2. Strategy Agent uses patterns to plan
    3. Outreach Agent finds new deals
    4. Deal Agent processes pending deals
    5. Content Agent drafts content
    6. Analytics Agent tracks performance
    
    This is the "autopilot" mode — runs everything without human triggers.
    """
    pipeline_steps = [
        ("memory_agent", "Run full memory analysis: analyze all deals, content, and store patterns"),
        ("strategy_agent", "Analyze market trends and creator performance, identify growth opportunities"),
        ("analytics_agent", "Check all connected platform analytics and generate performance report"),
    ]
    
    results = []
    for agent_name, task in pipeline_steps:
        result = await run_agent_by_name(agent_name, task, creator_id)
        results.append({"agent": agent_name, "result": result})
    
    return {"pipeline": "complete", "steps": results}


async def process_pending_deal(creator_id: int, deal_id: int) -> dict:
    """Process a pending deal through the full pipeline."""
    # Deal Agent analyzes
    deal_result = await run_agent_by_name(
        "deal_agent",
        f"Analyze and process deal #{deal_id}. Check db_lookup for deal details.",
        creator_id, entity_type="deal", entity_id=deal_id
    )
    return deal_result


async def process_approved_deal(creator_id: int, deal_id: int) -> dict:
    """
    When a deal is approved, trigger the full pipeline:
    1. Finance Agent creates invoice (real Stripe if connected)
    2. Content Agent drafts content for the deal
    3. Email Agent sends invoice to brand (if email connected)
    4. Scheduler Agent schedules content
    5. Notification Agent notifies the creator
    """
    results = {}

    # Get deal info
    with db_cursor() as conn:
        deal = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
        deal = dict(deal) if deal else {}
    brand_name = deal.get("brand_name", "the brand")
    deal_desc = deal.get("description", "")

    _log_activity("orchestrator", "pipeline_started",
                  f"🚀 Autonomous pipeline started for approved deal: {brand_name}",
                  "deal", deal_id, status="started")

    # 1. Finance Agent creates invoice
    try:
        finance_result = await run_agent_by_name(
            "finance_agent",
            f"Create invoice for approved deal #{deal_id} with {brand_name}. "
            f"Amount: ${deal.get('negotiated_amount') or deal.get('offer_amount', 0)}. "
            f"Check db_lookup for deal details. If Stripe is connected, create a real Stripe invoice. "
            f"If email is connected, send the invoice to the brand.",
            creator_id, entity_type="deal", entity_id=deal_id
        )
        results["finance"] = finance_result
        _log_activity("orchestrator", "pipeline_finance_done",
                      f"💰 Finance Agent completed invoice for {brand_name}",
                      "deal", deal_id, status="completed")
    except Exception as e:
        _log_activity("orchestrator", "pipeline_finance_error",
                      f"⚠️ Finance Agent error: {str(e)[:80]}",
                      "deal", deal_id, status="failed")
        results["finance"] = {"error": str(e)}

    # 2. Content Agent drafts content for the deal
    try:
        # Find the auto-created content brief for this deal
        with db_cursor() as conn:
            content = conn.execute(
                "SELECT id FROM content_items WHERE deal_id = ? AND status = 'brief' ORDER BY id DESC LIMIT 1",
                (deal_id,)
            ).fetchone()

        if content:
            content_id = content["id"]
            content_result = await run_agent_by_name(
                "content_agent",
                f"Draft content for approved deal with {brand_name}. "
                f"Content brief ID: {content_id}. "
                f"Deal description: {deal_desc}. "
                f"Research trending topics and write a full content draft optimized for the platform. "
                f"Use db_lookup to get the content item details, then write the draft.",
                creator_id, entity_type="content", entity_id=content_id
            )
            results["content"] = content_result
            _log_activity("orchestrator", "pipeline_content_done",
                          f"✍️ Content Agent drafted content for {brand_name}",
                          "deal", deal_id, status="completed")
        else:
            # No content brief yet — create one and draft it
            with db_cursor() as conn:
                cur = conn.execute("""
                    INSERT INTO content_items (creator_id, title, content_type, brief, platform, status, deal_id)
                    VALUES (?, ?, 'post', ?, 'instagram', 'brief', ?)
                """, (creator_id, f"Sponsored content for {brand_name}",
                      f"Create sponsored content for {brand_name} — {deal_desc}",
                      deal_id))
                content_id = cur.lastrowid

            content_result = await run_agent_by_name(
                "content_agent",
                f"Draft content for approved deal with {brand_name}. "
                f"Content brief ID: {content_id}. "
                f"Deal description: {deal_desc}. "
                f"Research trending topics and write a full content draft optimized for the platform.",
                creator_id, entity_type="content", entity_id=content_id
            )
            results["content"] = content_result
            _log_activity("orchestrator", "pipeline_content_done",
                          f"✍️ Content Agent drafted content for {brand_name}",
                          "deal", deal_id, status="completed")
    except Exception as e:
        _log_activity("orchestrator", "pipeline_content_error",
                      f"⚠️ Content Agent error: {str(e)[:80]}",
                      "deal", deal_id, status="failed")
        results["content"] = {"error": str(e)}

    # 3. Scheduler Agent schedules content
    try:
        scheduler_result = await run_agent_by_name(
            "scheduler_agent",
            f"Schedule content deliverables for approved deal #{deal_id} with {brand_name}. "
            f"Create calendar events for content deadlines.",
            creator_id, entity_type="deal", entity_id=deal_id
        )
        results["scheduler"] = scheduler_result
        _log_activity("orchestrator", "pipeline_scheduler_done",
                      f"📅 Scheduler Agent scheduled content for {brand_name}",
                      "deal", deal_id, status="completed")
    except Exception as e:
        _log_activity("orchestrator", "pipeline_scheduler_error",
                      f"⚠️ Scheduler Agent error: {str(e)[:80]}",
                      "deal", deal_id, status="failed")
        results["scheduler"] = {"error": str(e)}

    # 4. Notification Agent notifies
    try:
        notif_result = await run_agent_by_name(
            "notification_agent",
            f"Notify: Deal #{deal_id} with {brand_name} has been approved and fully processed. "
            f"Invoice created, content drafted, schedule set. "
            f"Send notification via connected platforms (Slack, Telegram, etc.).",
            creator_id
        )
        results["notification"] = notif_result
        _log_activity("orchestrator", "pipeline_notification_done",
                      f"🔔 Notification Agent sent alerts for {brand_name}",
                      "deal", deal_id, status="completed")
    except Exception as e:
        _log_activity("orchestrator", "pipeline_notification_error",
                      f"⚠️ Notification Agent error: {str(e)[:80]}",
                      "deal", deal_id, status="failed")
        results["notification"] = {"error": str(e)}

    _log_activity("orchestrator", "pipeline_complete",
                  f"✅ Autonomous pipeline complete for {brand_name} — all agents finished",
                  "deal", deal_id, status="completed")

    return {"pipeline": "deal_approved", "results": results}


async def process_pending_agent_tasks(creator_id: int = CREATOR_ID) -> dict:
    """Process all pending agent-to-agent tasks."""
    from agent_tools import get_pending_agent_tasks, complete_agent_task
    
    tasks = get_pending_agent_tasks(limit=10)
    if not tasks:
        return {"status": "no_pending_tasks"}
    
    results = []
    for task in tasks:
        result = await run_agent_by_name(
            task["to_agent"],
            task["task"],
            creator_id
        )
        complete_agent_task(task["id"], json.dumps(result)[:1000])
        results.append({"task_id": task["id"], "agent": task["to_agent"], "result": result})
    
    return {"processed": len(results), "results": results}


def get_agent_team_status() -> list:
    """Get status of all agents in the team."""
    with db_cursor() as conn:
        # Get last activity for each agent
        agents = []
        for name, info in AGENT_REGISTRY.items():
            last_activity = conn.execute(
                "SELECT * FROM agent_activities WHERE agent_name = ? ORDER BY created_at DESC LIMIT 1",
                (name,)
            ).fetchone()
            
            activity_count = conn.execute(
                "SELECT COUNT(*) as count FROM agent_activities WHERE agent_name = ?",
                (name,)
            ).fetchone()["count"]
            
            agents.append({
                "name": name,
                "display": info["display"],
                "icon": info["icon"],
                "type": info["type"],
                "desc": info["desc"],
                "last_active": dict(last_activity)["created_at"] if last_activity else None,
                "last_action": dict(last_activity)["summary"] if last_activity else None,
                "total_activities": activity_count,
            })
        return agents
