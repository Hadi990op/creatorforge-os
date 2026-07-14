"""
CreatorForge OS — Advanced Agent Module
========================================
4 specialized AI agents with real LLM reasoning, memory integration,
and automatic provider failover. Each agent:
  1. Gathers context (creator profile + historical patterns)
  2. Calls LLM with domain-specific system prompt
  3. Parses structured response
  4. Updates database + logs activity
  5. Routes to approval gate when needed
"""
import json
from datetime import datetime
from models import db_cursor
from llm_engine import (
    llm_chat, llm_chat_json, llm_chat_json_list,
    get_active_provider, get_provider_status,
)
from agent_prompts import (
    DEAL_AGENT_SYSTEM, DEAL_AGENT_PROMPT,
    CONTENT_AGENT_SYSTEM, CONTENT_AGENT_PROMPT,
    FINANCE_AGENT_SYSTEM, FINANCE_AGENT_PROMPT,
    MEMORY_AGENT_SYSTEM, MEMORY_AGENT_PROMPT,
)
from llm import (
    deal_agent_fallback, content_agent_fallback,
    finance_agent_fallback, memory_agent_fallback,
)


def _log_activity(agent_name: str, action: str, summary: str, entity_type: str = None,
                  entity_id: int = None, details: str = None, status: str = "completed"):
    with db_cursor() as conn:
        conn.execute("""
            INSERT INTO agent_activities (agent_name, action, entity_type, entity_id, summary, details, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (agent_name, action, entity_type, entity_id, summary, details, status))
        activity_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return activity_id


def _log_thinking(activity_id: int, agent_name: str, step: int, phase: str, thought: str):
    """Log a step in the agent's reasoning process — visible to the user."""
    with db_cursor() as conn:
        conn.execute("""
            INSERT INTO agent_thinking (activity_id, agent_name, step_number, phase, thought)
            VALUES (?, ?, ?, ?, ?)
        """, (activity_id, agent_name, step, phase, thought))


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
    """Get relevant patterns from memory to inject into agent prompts."""
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


# ═══════════════════════════════════════════════════
#  DEAL AGENT — Brand Deal Analysis & Negotiation
# ═══════════════════════════════════════════════════

async def deal_agent_analyze(creator_id: int, deal_id: int) -> dict:
    """
    Analyze an inbound brand deal using real AI:
    - Assesses brand-creator fit
    - Benchmarks price against market rates
    - Generates counter-offer with negotiated terms
    - Routes to approval gate
    """
    with db_cursor() as conn:
        creator = _get_creator(conn, creator_id)
        deal = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
        if not creator or not deal:
            return {"error": "Creator or deal not found"}
        deal = dict(deal)
        memory_context = _get_memory_context(conn, creator_id)

    _log_activity("deal_agent", "analyzing_deal",
                  f"🤝 Deal Agent analyzing inbound deal from {deal['brand_name']} — checking brand fit, benchmarking price, preparing counter-offer...",
                  "deal", deal_id, status="started")

    # Log thinking steps so user can see what the agent is doing
    act_id = _log_activity("deal_agent", "thinking",
                           f"Deal Agent processing deal from {deal['brand_name']}",
                           "deal", deal_id, status="started")

    _log_thinking(act_id, "deal_agent", 1, "data_gathering",
                 f"📥 Reading deal details: {deal['brand_name']} ({deal.get('brand_type', 'unknown')}) "
                 f"offers ${deal.get('offer_amount', 0):,.0f} for {deal.get('deal_type', 'sponsorship')}. "
                 f"Creator: {creator['name']} with {creator['followers']:,} followers in '{creator.get('niche', 'general')}' niche.")
    _log_thinking(act_id, "deal_agent", 2, "context_loading",
                 f"🧠 Loading memory patterns for context... {'Found ' + str(len(memory_context.split(chr(10)))) + ' lines of context' if memory_context != 'No historical patterns available yet.' else 'No historical patterns yet — first analysis.'}")
    _log_thinking(act_id, "deal_agent", 3, "ai_analysis",
                 f"🤖 Sending to AI: brand fit assessment + price benchmarking + negotiation strategy. "
                 f"Analyzing how {deal['brand_name']} aligns with {creator['name']}'s audience...")
    _log_thinking(act_id, "deal_agent", 4, "ai_calling",
                 f"⏳ Waiting for AI response... (this takes a few seconds)")

    # Build prompt with all context
    prompt = DEAL_AGENT_PROMPT.format(
        creator_name=creator['name'],
        creator_handle=creator['handle'],
        creator_niche=creator.get('niche', 'general'),
        creator_followers=creator['followers'],
        creator_bio=creator.get('bio', ''),
        brand_name=deal['brand_name'],
        brand_type=deal.get('brand_type', 'unknown'),
        deal_type=deal.get('deal_type', 'sponsorship'),
        offer_amount=deal.get('offer_amount', 0),
        description=deal.get('description', ''),
        memory_context=memory_context,
    )

    # Try real AI first
    analysis = await llm_chat_json(prompt, system=DEAL_AGENT_SYSTEM, max_tokens=1200)

    # Fall back to rule-based if AI fails
    if not analysis:
        print("[Deal Agent] LLM unavailable, using rule-based fallback")
        analysis = deal_agent_fallback(
            deal['brand_name'], deal.get('brand_type'), deal.get('offer_amount', 0),
            deal.get('deal_type'), creator.get('niche'), creator['followers'],
            deal.get('description', '')
        )
    else:
        # Ensure all required fields exist
        analysis.setdefault('fit_score', 0.5)
        analysis.setdefault('fit_reasoning', 'Analysis complete.')
        analysis.setdefault('recommendation', 'moderate_fit')
        analysis.setdefault('price_assessment', 'fair market value')
        analysis.setdefault('benchmark_price', 0)
        analysis.setdefault('negotiated_amount', deal.get('offer_amount', 0))
        analysis.setdefault('negotiated_terms', 'Standard terms.')
        analysis.setdefault('agent_analysis', 'Deal analyzed.')
        # Ensure numeric types
        analysis['fit_score'] = float(analysis['fit_score'])
        analysis['benchmark_price'] = float(analysis.get('benchmark_price', 0))
        analysis['negotiated_amount'] = float(analysis.get('negotiated_amount', 0))

    # Update deal with analysis
    with db_cursor() as conn:
        conn.execute("""
            UPDATE deals SET status = 'analyzed', fit_score = ?, fit_reasoning = ?,
            negotiated_amount = ?, negotiated_terms = ?, agent_analysis = ?,
            updated_at = datetime('now')
            WHERE id = ?
        """, (analysis['fit_score'], analysis['fit_reasoning'],
              analysis.get('negotiated_amount'), analysis.get('negotiated_terms'),
              analysis['agent_analysis'], deal_id))

    rec = analysis.get('recommendation', "moderate_fit")
    provider = get_active_provider()
    summary = f"🤝 Deal from {deal['brand_name']} analyzed: {analysis['fit_score']:.0%} fit — {rec.replace('_', ' ')} (via {provider})"

    _log_thinking(act_id, "deal_agent", 5, "result",
                  f"✅ AI analysis complete! Fit score: {analysis['fit_score']:.0%} — {rec.replace('_', ' ')}. "
                  f"Price assessment: {analysis.get('price_assessment', 'N/A')}. "
                  f"Counter-offer: ${analysis.get('negotiated_amount', 0):,.0f} (original: ${deal.get('offer_amount', 0):,.0f})")

    _log_activity("deal_agent", "deal_analyzed", summary,
                  "deal", deal_id,
                  details=json.dumps(analysis), status="completed")

    # Route to approval if not off-brand
    if rec != "off_brand":
        approval_summary = (
            f"**{deal['brand_name']}** — ${analysis.get('negotiated_amount', 0):,.0f}\n"
            f"Fit: {analysis['fit_score']:.0%} | {rec.replace('_', ' ')}\n"
            f"Price: {analysis.get('price_assessment', 'N/A')}\n\n"
            f"{analysis['fit_reasoning']}\n\n"
            f"**Counter-offer:** {analysis.get('negotiated_terms', 'N/A')}"
        )
        approval_id = _create_approval("deal", deal_id, "deal_agent",
                                       f"Deal: {deal['brand_name']}", approval_summary)

        with db_cursor() as conn:
            conn.execute("UPDATE deals SET status = 'negotiating', needs_approval = 1 WHERE id = ?", (deal_id,))

        _log_activity("deal_agent", "routed_for_approval",
                      f"⏳ Deal from {deal['brand_name']} routed for creator approval — counter-offer: ${analysis.get('negotiated_amount', 0):,.0f}",
                      "deal", deal_id, status="awaiting_approval")
        return {"analysis": analysis, "approval_id": approval_id, "provider": provider}
    else:
        with db_cursor() as conn:
            conn.execute("UPDATE deals SET status = 'declined', needs_approval = 0 WHERE id = ?", (deal_id,))

        _log_activity("deal_agent", "auto_declined",
                      f"❌ Deal from {deal['brand_name']} auto-declined (off-brand, {analysis['fit_score']:.0%} fit) — {analysis.get('fit_reasoning', '')[:100]}",
                      "deal", deal_id, status="completed")
        return {"analysis": analysis, "auto_declined": True, "provider": provider}


# ═══════════════════════════════════════════════════
#  CONTENT AGENT — Content Drafting & Platform Optimization
# ═══════════════════════════════════════════════════

async def content_agent_draft(creator_id: int, content_id: int) -> dict:
    """
    Generate content from a brief using real AI:
    - Writes authentic content matching creator's voice
    - Optimizes for the target platform
    - Suggests hashtags and platform-specific notes
    """
    with db_cursor() as conn:
        creator = _get_creator(conn, creator_id)
        content = conn.execute("SELECT * FROM content_items WHERE id = ?", (content_id,)).fetchone()
        if not creator or not content:
            return {"error": "Creator or content not found"}
        content = dict(content)
        memory_context = _get_memory_context(conn, creator_id)

    _log_activity("content_agent", "drafting_content",
                  f"✍️ Content Agent drafting '{content['title']}' for {content['platform']} — analyzing brief, optimizing for platform...",
                  "content", content_id, status="started")

    act_id = _log_activity("content_agent", "thinking",
                           f"Content Agent processing '{content['title']}'",
                           "content", content_id, status="started")

    _log_thinking(act_id, "content_agent", 1, "data_gathering",
                  f"📥 Reading brief: '{content['title']}' for {content['platform']}. "
                  f"Content type: {content.get('content_type', 'post')}. "
                  f"Creator: {creator['name']} ({creator.get('niche', 'general')} niche).")
    _log_thinking(act_id, "content_agent", 2, "strategy",
                  f"🎨 Planning content approach: matching {creator['name']}'s voice and optimizing for {content['platform']}. "
                  f"Loading memory patterns for style reference...")
    _log_thinking(act_id, "content_agent", 3, "ai_writing",
                  f"🤖 AI is now writing the content... generating authentic draft with platform-specific formatting, hashtags, and notes.")
    _log_thinking(act_id, "content_agent", 4, "ai_calling",
                  f"⏳ Waiting for AI response... (crafting content, this takes a few seconds)")

    prompt = CONTENT_AGENT_PROMPT.format(
        creator_name=creator['name'],
        creator_niche=creator.get('niche', 'general'),
        creator_bio=creator.get('bio', ''),
        title=content['title'],
        content_type=content.get('content_type', 'post'),
        platform=content.get('platform', 'instagram'),
        brief=content.get('brief', ''),
        memory_context=memory_context,
    )

    # Try real AI first
    draft_result = await llm_chat_json(prompt, system=CONTENT_AGENT_SYSTEM, max_tokens=1200)

    if not draft_result:
        print("[Content Agent] LLM unavailable, using rule-based fallback")
        draft_result = content_agent_fallback(
            content['title'], content.get('brief', ''), content['content_type'],
            content['platform'], creator.get('niche')
        )
    else:
        draft_result.setdefault('draft', '')
        draft_result.setdefault('hashtags', '')
        draft_result.setdefault('platform_notes', '')
        draft_result.setdefault('agent_reasoning', 'Content drafted by AI agent.')

    # Update content with draft
    with db_cursor() as conn:
        conn.execute("""
            UPDATE content_items SET draft = ?, status = 'draft_ready',
            agent_reasoning = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (draft_result['draft'], draft_result.get('agent_reasoning', ''), content_id))

    provider = get_active_provider()
    summary = f"✍️ Content draft ready: '{content['title']}' for {content['platform']} — {draft_result.get('agent_reasoning', '')[:80]} (via {provider})"

    _log_thinking(act_id, "content_agent", 5, "result",
                  f"✅ Content drafted! {len(draft_result.get('draft', ''))} characters written for {content['platform']}. "
                  f"Hashtags: {draft_result.get('hashtags', 'none')[:60]}. "
                  f"Ready for creator approval.")

    _log_activity("content_agent", "draft_ready", summary,
                  "content", content_id,
                  details=json.dumps(draft_result), status="completed")

    # Route to approval
    draft_preview = draft_result['draft'][:300] if len(draft_result['draft']) > 300 else draft_result['draft']
    approval_summary = (
        f"**{content['title']}** ({content['platform']})\n\n"
        f"{draft_preview}\n\n"
        f"**Hashtags:** {draft_result.get('hashtags', 'N/A')}\n"
        f"**Platform notes:** {draft_result.get('platform_notes', 'N/A')}"
    )
    approval_id = _create_approval("content", content_id, "content_agent",
                                   f"Content: {content['title']}", approval_summary)

    _log_activity("content_agent", "routed_for_approval",
                  f"⏳ Content '{content['title']}' routed for creator approval",
                  "content", content_id, status="awaiting_approval")

    return {"draft": draft_result, "approval_id": approval_id, "provider": provider}


# ═══════════════════════════════════════════════════
#  FINANCE AGENT — Invoice Generation & Payment Management
# ═══════════════════════════════════════════════════

async def finance_agent_invoice(creator_id: int, invoice_id: int) -> dict:
    """
    Generate professional invoice details using real AI:
    - Creates detailed line items
    - Sets payment terms and due dates
    - Adds professional notes
    """
    with db_cursor() as conn:
        creator = _get_creator(conn, creator_id)
        invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not creator or not invoice:
            return {"error": "Creator or invoice not found"}
        invoice = dict(invoice)
        memory_context = _get_memory_context(conn, creator_id)

    _log_activity("finance_agent", "generating_invoice",
                  f"💰 Finance Agent generating invoice for {invoice['client_name']} — creating line items, setting terms...",
                  "invoice", invoice_id, status="started")

    act_id = _log_activity("finance_agent", "thinking",
                           f"Finance Agent processing invoice for {invoice['client_name']}",
                           "invoice", invoice_id, status="started")

    _log_thinking(act_id, "finance_agent", 1, "data_gathering",
                  f"📋 Invoice details: {invoice['client_name']} for ${invoice['amount']:,.0f}. "
                  f"Creator: {creator['name']}. Today: {today}.")
    _log_thinking(act_id, "finance_agent", 2, "analysis",
                  f"💡 Analyzing deal type and creating line items — breaking down the total into specific services, usage rights, and fees...")
    _log_thinking(act_id, "finance_agent", 3, "ai_generating",
                  f"🤖 AI generating professional invoice with itemized breakdown, payment terms, and due date calculation...")
    _log_thinking(act_id, "finance_agent", 4, "ai_calling",
                  f"⏳ Waiting for AI response... (creating invoice structure)")

    today = datetime.now().strftime("%Y-%m-%d")
    prompt = FINANCE_AGENT_PROMPT.format(
        creator_name=creator['name'],
        creator_handle=creator['handle'],
        client_name=invoice['client_name'],
        amount=invoice['amount'],
        deal_type=invoice.get('status', 'sponsorship'),
        today=today,
        memory_context=memory_context,
    )

    # Try real AI first
    invoice_result = await llm_chat_json(prompt, system=FINANCE_AGENT_SYSTEM, max_tokens=800)

    if not invoice_result:
        print("[Finance Agent] LLM unavailable, using rule-based fallback")
        invoice_result = finance_agent_fallback(
            invoice['client_name'], invoice['amount'], invoice.get('status'),
            creator['name']
        )
    else:
        invoice_result.setdefault('items', '[]')
        invoice_result.setdefault('due_date', (datetime.now().strftime("%Y-%m-%d")))
        invoice_result.setdefault('agent_notes', 'Invoice generated.')

    # Update invoice
    with db_cursor() as conn:
        conn.execute("""
            UPDATE invoices SET items = ?, due_date = ?, agent_notes = ?,
            status = 'pending_approval'
            WHERE id = ?
        """, (invoice_result.get('items', '[]'), invoice_result.get('due_date'),
              invoice_result.get('agent_notes'), invoice_id))

    provider = get_active_provider()
    summary = f"💰 Invoice ready for {invoice['client_name']}: ${invoice['amount']:,.0f} — due {invoice_result.get('due_date', 'N/A')} (via {provider})"

    items_list = json.loads(invoice_result.get('items', '[]')) if isinstance(invoice_result.get('items'), str) else invoice_result.get('items', [])
    _log_thinking(act_id, "finance_agent", 5, "result",
                  f"✅ Invoice generated! {len(items_list)} line items created. "
                  f"Due date: {invoice_result.get('due_date', 'N/A')}. "
                  f"Total: ${invoice['amount']:,.0f}. Ready for creator approval.")

    _log_activity("finance_agent", "invoice_ready", summary,
                  "invoice", invoice_id,
                  details=json.dumps(invoice_result), status="completed")

    # Route to approval
    approval_summary = (
        f"**{invoice['client_name']}** — ${invoice['amount']:,.0f}\n"
        f"Due: {invoice_result.get('due_date', 'N/A')}\n\n"
        f"{invoice_result.get('agent_notes', '')}"
    )
    approval_id = _create_approval("invoice", invoice_id, "finance_agent",
                                   f"Invoice: {invoice['client_name']}", approval_summary)

    _log_activity("finance_agent", "routed_for_approval",
                  f"⏳ Invoice for {invoice['client_name']} routed for creator approval",
                  "invoice", invoice_id, status="awaiting_approval")

    return {"invoice": invoice_result, "approval_id": approval_id, "provider": provider}


# ═══════════════════════════════════════════════════
#  MEMORY AGENT — Pattern Learning & Intelligence
# ═══════════════════════════════════════════════════

async def memory_agent_learn(creator_id: int) -> dict:
    """
    Analyze all historical data to extract patterns using real AI:
    - Deal acceptance patterns
    - Brand type preferences
    - Content performance insights
    - Pricing strategies
    """
    with db_cursor() as conn:
        creator = _get_creator(conn, creator_id)
        if not creator:
            return {"error": "Creator not found"}

        deals = [dict(r) for r in conn.execute(
            "SELECT * FROM deals WHERE creator_id = ? AND status != 'pending_analysis'",
            (creator_id,)
        ).fetchall()]
        content_items = [dict(r) for r in conn.execute(
            "SELECT * FROM content_items WHERE creator_id = ?",
            (creator_id,)
        ).fetchall()]
        existing = [dict(r) for r in conn.execute(
            "SELECT pattern_type, pattern_key, pattern_value, insight FROM memory_patterns WHERE creator_id = ?",
            (creator_id,)
        ).fetchall()]

    _log_activity("memory_agent", "analyzing_patterns",
                  f"🧠 Memory Agent analyzing {len(deals)} deals and {len(content_items)} content items — extracting patterns, scoring confidence...",
                  "creator", creator_id, status="started")

    act_id = _log_activity("memory_agent", "thinking",
                           f"Memory Agent analyzing {len(deals)} deals and {len(content_items)} content items",
                           "creator", creator_id, status="started")

    _log_thinking(act_id, "memory_agent", 1, "data_gathering",
                  f"📊 Gathering data: {len(deals)} deals, {len(content_items)} content items, {len(existing)} existing patterns. "
                  f"Creator: {creator['name']} ({creator.get('niche', 'general')}, {creator['followers']:,} followers)")
    _log_thinking(act_id, "memory_agent", 2, "pattern_mining",
                  f"🔍 Mining patterns: deal acceptance rates, brand type preferences, pricing trends, content performance...")
    _log_thinking(act_id, "memory_agent", 3, "ai_analysis",
                  f"🤖 AI analyzing all data to extract actionable insights — what brands fit best, what price ranges work, what content performs...")
    _log_thinking(act_id, "memory_agent", 4, "ai_calling",
                  f"⏳ Waiting for AI response... (analyzing patterns, this takes a few seconds)")

    # Prepare summaries for the prompt
    deal_summary = json.dumps([{
        "brand": d["brand_name"], "type": d.get("brand_type"),
        "amount": d.get("offer_amount"), "status": d["status"],
        "fit_score": d.get("fit_score"), "negotiated": d.get("negotiated_amount")
    } for d in deals[:20]], indent=2) if deals else "No deals yet."

    content_summary = json.dumps([{
        "title": c["title"], "platform": c.get("platform"),
        "status": c["status"], "type": c.get("content_type")
    } for c in content_items[:20]], indent=2) if content_items else "No content yet."

    existing_patterns = ""
    if existing:
        existing_patterns = "EXISTING PATTERNS (update or replace these):\n" + \
            "\n".join(f"- {p['pattern_type']}/{p['pattern_key']}: {p['pattern_value']}" for p in existing)
    else:
        existing_patterns = "No existing patterns — this is the first analysis."

    prompt = MEMORY_AGENT_PROMPT.format(
        creator_niche=creator.get('niche', 'general'),
        creator_followers=creator['followers'],
        deal_count=len(deals),
        deal_summary=deal_summary,
        content_count=len(content_items),
        content_summary=content_summary,
        existing_patterns=existing_patterns,
    )

    # Try real AI first
    patterns = await llm_chat_json_list(prompt, system=MEMORY_AGENT_SYSTEM, max_tokens=1200)

    if not patterns:
        print("[Memory Agent] LLM unavailable, using rule-based fallback")
        patterns = memory_agent_fallback(deals, content_items, creator.get('niche'))
    else:
        # Ensure each pattern has required fields
        for p in patterns:
            p.setdefault('pattern_type', 'general')
            p.setdefault('pattern_key', 'pattern')
            p.setdefault('pattern_value', 'N/A')
            p.setdefault('confidence', 0.5)
            p.setdefault('sample_count', 1)
            p.setdefault('insight', '')
            p['confidence'] = float(p.get('confidence', 0.5))
            p['sample_count'] = int(p.get('sample_count', 1))

    # Clear old patterns, insert new ones
    with db_cursor() as conn:
        conn.execute("DELETE FROM memory_patterns WHERE creator_id = ?", (creator_id,))
        for p in patterns:
            conn.execute("""
                INSERT INTO memory_patterns (creator_id, pattern_type, pattern_key, pattern_value,
                confidence, sample_count, insight)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (creator_id, p['pattern_type'], p['pattern_key'], p['pattern_value'],
                  p.get('confidence', 0.5), p.get('sample_count', 1), p.get('insight', '')))

    provider = get_active_provider()
    summary = f"🧠 Learned {len(patterns)} patterns from {len(deals)} deals and {len(content_items)} content items (via {provider})"

    _log_thinking(act_id, "memory_agent", 5, "result",
                  f"✅ Pattern learning complete! {len(patterns)} insights extracted. "
                  f"Patterns: {', '.join(p.get('pattern_type', '?') for p in patterns[:5])}")

    _log_activity("memory_agent", "patterns_learned", summary,
                  "creator", creator_id,
                  details=json.dumps(patterns), status="completed")

    return {"patterns": patterns, "count": len(patterns), "provider": provider}


# ═══════════════════════════════════════════════════
#  APPROVAL RESOLVER
# ═══════════════════════════════════════════════════

def resolve_approval(approval_id: int, decision: str) -> dict:
    """Resolve an approval gate — updates the underlying entity."""
    if decision not in ("approved", "declined"):
        return {"error": "Decision must be 'approved' or 'declined'"}

    auto_invoice_id = None
    auto_invoice_brand = None

    with db_cursor() as conn:
        approval = conn.execute(
            "SELECT * FROM approval_queue WHERE id = ? AND status = 'pending'",
            (approval_id,)
        ).fetchone()
        if not approval:
            return {"error": "Approval not found or already resolved"}
        approval = dict(approval)

        conn.execute("""
            UPDATE approval_queue SET status = ?, resolved_at = datetime('now')
            WHERE id = ?
        """, (decision, approval_id))

        entity_type = approval['entity_type']
        entity_id = approval['entity_id']
        agent_name = approval['agent_name']

        if entity_type == "deal":
            if decision == "approved":
                conn.execute("""
                    UPDATE deals SET status = 'approved', updated_at = datetime('now')
                    WHERE id = ?
                """, (entity_id,))
                # Auto-generate invoice
                deal = conn.execute("SELECT * FROM deals WHERE id = ?", (entity_id,)).fetchone()
                if deal:
                    deal = dict(deal)
                    cur = conn.execute("""
                        INSERT INTO invoices (creator_id, deal_id, client_name, amount, status)
                        VALUES (?, ?, ?, ?, 'draft')
                    """, (deal['creator_id'], entity_id, deal['brand_name'],
                          deal.get('negotiated_amount') or deal.get('offer_amount', 0)))
                    auto_invoice_id = cur.lastrowid
                    auto_invoice_brand = deal['brand_name']
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

    if auto_invoice_id:
        _log_activity("finance_agent", "auto_invoice_created",
                      f"💰 Auto-generated invoice #{auto_invoice_id} for approved deal with {auto_invoice_brand}",
                      "invoice", auto_invoice_id, status="completed")

    _log_activity(agent_name, f"approval_{decision}",
                  f"{'✅' if decision == 'approved' else '❌'} Creator {decision} {entity_type} #{entity_id}",
                  entity_type, entity_id, status=decision)

    return {"status": "resolved", "decision": decision, "entity_type": entity_type, "entity_id": entity_id}
