"""
CreatorForge OS — FastAPI Main Application
The Agentic Operating System for Creators
"""
import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Ensure backend dir is in path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from models import init_db, db_cursor
from seed import seed
from agents_v2 import (
    deal_agent_analyze, content_agent_draft,
    finance_agent_invoice, memory_agent_learn,
    resolve_approval,
)
from llm import HAS_LLM
from llm_engine import (
    get_provider_status, add_provider_key, remove_provider_key,
    reload_providers, get_active_provider,
)

app = FastAPI(title="CreatorForge OS", version="2.0.0",
              description="The Agentic Operating System for Creators — ReAct Agent Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()
    # Don't auto-seed — user onboards through the UI
    # But seed demo data only if no creator exists AND seed.py is explicitly called
    with db_cursor() as conn:
        count = conn.execute("SELECT COUNT(*) FROM creators").fetchone()[0]
    if count == 0:
        print("[CreatorForge] No creator found — waiting for onboarding via UI")


# ─── Dashboard ───

@app.get("/api/dashboard")
async def dashboard():
    """Main dashboard data — overview of everything."""
    with db_cursor() as conn:
        creator = conn.execute("SELECT * FROM creators LIMIT 1").fetchone()
        if not creator:
            return {"needs_onboarding": True}
        creator = dict(creator)

        products = [dict(r) for r in conn.execute("SELECT * FROM products WHERE creator_id = ?", (creator["id"],)).fetchall()]
        deals_active = [dict(r) for r in conn.execute(
            "SELECT * FROM deals WHERE creator_id = ? AND status IN ('pending_analysis', 'analyzed', 'negotiating')",
            (creator["id"],)
        ).fetchall()]
        deals_closed = [dict(r) for r in conn.execute(
            "SELECT * FROM deals WHERE creator_id = ? AND status IN ('approved', 'declined', 'closed')",
            (creator["id"],)
        ).fetchall()]
        content_items = [dict(r) for r in conn.execute(
            "SELECT * FROM content_items WHERE creator_id = ?", (creator["id"],)
        ).fetchall()]
        invoices = [dict(r) for r in conn.execute(
            "SELECT * FROM invoices WHERE creator_id = ?", (creator["id"],)
        ).fetchall()]
        pending_invoices = [dict(r) for r in conn.execute(
            "SELECT * FROM invoices WHERE creator_id = ? AND status IN ('draft', 'pending_approval')",
            (creator["id"],)
        ).fetchall()]
        activities = [dict(r) for r in conn.execute(
            "SELECT * FROM agent_activities ORDER BY created_at DESC LIMIT 20"
        ).fetchall()]
        pending_approvals = [dict(r) for r in conn.execute(
            "SELECT * FROM approval_queue WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()]
        patterns = [dict(r) for r in conn.execute(
            "SELECT * FROM memory_patterns WHERE creator_id = ?", (creator["id"],)
        ).fetchall()]
        recent_thinking = [dict(r) for r in conn.execute(
            """SELECT t.*, a.summary as activity_summary
               FROM agent_thinking t
               LEFT JOIN agent_activities a ON t.activity_id = a.id
               ORDER BY t.created_at DESC LIMIT 30"""
        ).fetchall()]
        documents = [dict(r) for r in conn.execute(
            "SELECT * FROM documents WHERE creator_id = ? ORDER BY created_at DESC LIMIT 20",
            (creator["id"],)
        ).fetchall()]

        total_sales = sum(p["sales_count"] for p in products)
        total_revenue_from_sales = sum(p["price"] * p["sales_count"] for p in products)
        total_deal_revenue = sum(
            (d.get("negotiated_amount") or d.get("offer_amount") or 0)
            for d in deals_closed if d["status"] == "approved"
        )

    return {
        "creator": creator,
        "stats": {
            "followers": creator["followers"],
            "monthly_revenue": creator["monthly_revenue"],
            "cleared_revenue": creator["cleared_revenue"],
            "products_count": len(products),
            "total_sales": total_sales,
            "total_product_revenue": total_revenue_from_sales,
            "total_deal_revenue": total_deal_revenue,
            "active_deals": len(deals_active),
            "closed_deals": len(deals_closed),
            "content_count": len(content_items),
            "published_content": len([c for c in content_items if c["status"] == "published"]),
            "pending_approvals": len(pending_approvals),
            "patterns_count": len(patterns),
            "llm_enabled": True,
            "active_provider": get_active_provider(),
            "providers": get_provider_status(),
        },
        "products": products,
        "active_deals": deals_active,
        "pending_approvals": pending_approvals,
        "recent_activities": activities,
        "patterns": patterns,
        "recent_thinking": recent_thinking,
        "documents": documents,
    }


# ─── Creator ───

@app.get("/api/creator")
async def get_creator():
    with db_cursor() as conn:
        creator = conn.execute("SELECT * FROM creators LIMIT 1").fetchone()
        if not creator:
            raise HTTPException(404, "No creator found")
        return dict(creator)

@app.put("/api/creator")
async def update_creator(data: dict):
    with db_cursor() as conn:
        creator = conn.execute("SELECT * FROM creators LIMIT 1").fetchone()
        if not creator:
            raise HTTPException(404, "No creator found")
        cid = creator["id"]
        for field in ["name", "handle", "bio", "niche", "followers", "monthly_revenue", "cleared_revenue", "avatar"]:
            if field in data:
                conn.execute(f"UPDATE creators SET {field} = ? WHERE id = ?", (data[field], cid))
        return {"status": "updated"}


# ─── Products / Storefront ───

@app.get("/api/products")
async def get_products():
    with db_cursor() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY sales_count DESC").fetchall()
        return [dict(r) for r in rows]

@app.post("/api/products")
async def add_product(data: dict):
    with db_cursor() as conn:
        creator = conn.execute("SELECT id FROM creators LIMIT 1").fetchone()
        if not creator:
            raise HTTPException(404, "No creator")
        cur = conn.execute("""
            INSERT INTO products (creator_id, title, description, price, sales_count, category, image_emoji)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (creator["id"], data.get("title", ""), data.get("description", ""),
              data.get("price", 0), data.get("sales_count", 0),
              data.get("category", ""), data.get("image_emoji", "📦")))
        return {"id": cur.lastrowid, "status": "created"}

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: int):
    with db_cursor() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        return {"status": "deleted"}


# ─── Deals ───

@app.get("/api/deals")
async def get_deals(status: Optional[str] = None):
    with db_cursor() as conn:
        if status:
            rows = conn.execute("SELECT * FROM deals WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM deals ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

@app.post("/api/deals")
async def add_deal(data: dict):
    with db_cursor() as conn:
        creator = conn.execute("SELECT id FROM creators LIMIT 1").fetchone()
        if not creator:
            raise HTTPException(404, "No creator")
        cur = conn.execute("""
            INSERT INTO deals (creator_id, brand_name, brand_type, deal_type, offer_amount, description, status, needs_approval)
            VALUES (?, ?, ?, ?, ?, ?, 'pending_analysis', 0)
        """, (creator["id"], data.get("brand_name", ""), data.get("brand_type", ""),
              data.get("deal_type", "sponsorship"), data.get("offer_amount", 0),
              data.get("description", "")))
        deal_id = cur.lastrowid
    return {"id": deal_id, "status": "created", "message": "Deal added. Run /api/agents/deal/analyze to process."}

@app.post("/api/agents/deal/analyze/{deal_id}")
async def analyze_deal(deal_id: int):
    creator = None
    with db_cursor() as conn:
        creator = conn.execute("SELECT id FROM creators LIMIT 1").fetchone()
    if not creator:
        raise HTTPException(404, "No creator")
    result = await deal_agent_analyze(creator["id"], deal_id)
    return result


@app.post("/api/deals/{deal_id}/approve")
async def approve_deal(deal_id: int):
    """Approve a deal directly (from Deals tab) and trigger the full autonomous pipeline."""
    deal = None
    approval_id = None

    with db_cursor() as conn:
        deal_row = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
        if not deal_row:
            raise HTTPException(404, "Deal not found")
        deal = dict(deal_row)

        # Check if there's a pending approval for this deal
        approval = conn.execute(
            "SELECT id FROM approval_queue WHERE entity_type = 'deal' AND entity_id = ? AND status = 'pending'",
            (deal_id,)
        ).fetchone()

        if approval:
            approval_id = approval["id"]
        else:
            # No approval in queue — approve directly and create invoice + content
            conn.execute("UPDATE deals SET status = 'approved', updated_at = datetime('now') WHERE id = ?", (deal_id,))
            conn.execute("""
                INSERT INTO invoices (creator_id, deal_id, client_name, amount, status, agent_notes)
                VALUES (?, ?, ?, ?, 'draft', 'Auto-generated upon deal approval')
            """, (deal["creator_id"], deal_id, deal["brand_name"],
                  deal.get("negotiated_amount") or deal.get("offer_amount", 0)))
            conn.execute("""
                INSERT INTO content_items (creator_id, title, content_type, brief, platform, status, deal_id)
                VALUES (?, ?, 'post', ?, 'instagram', 'brief', ?)
            """, (deal["creator_id"], f"Sponsored content for {deal['brand_name']}",
                  f"Create sponsored content for {deal['brand_name']} — {deal.get('description', '')}",
                  deal_id))

    # Log activities (outside the DB context to avoid lock)
    brand_name = deal["brand_name"]
    _log_activity_act("deal_agent", "deal_approved",
                  f"✅ Deal with {brand_name} approved — triggering autonomous pipeline",
                  "deal", deal_id, status="completed")
    _log_activity_act("finance_agent", "auto_invoice_created",
                  f"💰 Auto-generated invoice for {brand_name}",
                  "deal", deal_id, status="completed")
    _log_activity_act("content_agent", "auto_content_scheduled",
                  f"✍️ Auto-created content brief for {brand_name} — ready in Content tab",
                  "deal", deal_id, status="completed")

    # If there was an approval, resolve it (this triggers the pipeline)
    if approval_id:
        from agents_v2 import resolve_approval
        result = await resolve_approval(approval_id, "approved")
    else:
        # Trigger the autonomous pipeline directly
        result = {"status": "approved", "deal_id": deal_id}
        try:
            from agent_team import process_approved_deal
            creator_id = deal.get("creator_id", 1)
            asyncio.create_task(process_approved_deal(creator_id, deal_id))
        except Exception as e:
            _log_activity_act("orchestrator", "pipeline_error",
                          f"⚠️ Pipeline trigger error: {str(e)[:100]}",
                          "deal", deal_id, status="failed")

    return {"status": "approved", "deal_id": deal_id, "message": "Deal approved. Autonomous pipeline triggered — finance, content, and notifications are being processed."}


@app.post("/api/deals/{deal_id}/decline")
async def decline_deal(deal_id: int):
    """Decline a deal directly (from Deals tab)."""
    with db_cursor() as conn:
        deal = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
        if not deal:
            raise HTTPException(404, "Deal not found")
        deal = dict(deal)
        conn.execute("UPDATE deals SET status = 'declined', updated_at = datetime('now') WHERE id = ?", (deal_id,))
        # Also resolve any pending approval
        approval = conn.execute(
            "SELECT id FROM approval_queue WHERE entity_type = 'deal' AND entity_id = ? AND status = 'pending'",
            (deal_id,)
        ).fetchone()
        if approval:
            conn.execute("UPDATE approval_queue SET status = 'declined', resolved_at = datetime('now') WHERE id = ?", (approval["id"],))

    _log_activity_act("deal_agent", "deal_declined",
                      f"❌ Deal with {deal['brand_name']} declined",
                      "deal", deal_id, status="completed")
    return {"status": "declined", "deal_id": deal_id}


def _log_activity_act(agent_name: str, action: str, summary: str,
                      entity_type: str = None, entity_id: int = None, status: str = "completed"):
    """Local activity logger to avoid circular imports."""
    from models import db_cursor
    with db_cursor() as conn:
        conn.execute("""
            INSERT INTO agent_activities (agent_name, action, summary, entity_type, entity_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (agent_name, action, summary, entity_type, entity_id, status))

@app.delete("/api/deals/{deal_id}")
async def delete_deal(deal_id: int):
    with db_cursor() as conn:
        conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
        conn.execute("DELETE FROM approval_queue WHERE entity_type = 'deal' AND entity_id = ?", (deal_id,))
        return {"status": "deleted"}


# ─── Content ───

@app.get("/api/content")
async def get_content(status: Optional[str] = None):
    with db_cursor() as conn:
        if status:
            rows = conn.execute("SELECT * FROM content_items WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM content_items ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

@app.post("/api/content")
async def add_content(data: dict):
    with db_cursor() as conn:
        creator = conn.execute("SELECT id FROM creators LIMIT 1").fetchone()
        if not creator:
            raise HTTPException(404, "No creator")
        cur = conn.execute("""
            INSERT INTO content_items (creator_id, title, content_type, brief, status, platform)
            VALUES (?, ?, ?, ?, 'brief', ?)
        """, (creator["id"], data.get("title", ""), data.get("content_type", "post"),
              data.get("brief", ""), data.get("platform", "instagram")))
        return {"id": cur.lastrowid, "status": "created"}

@app.post("/api/agents/content/draft/{content_id}")
async def draft_content(content_id: int):
    creator = None
    with db_cursor() as conn:
        creator = conn.execute("SELECT id FROM creators LIMIT 1").fetchone()
    if not creator:
        raise HTTPException(404, "No creator")
    result = await content_agent_draft(creator["id"], content_id)
    return result

# Alias: frontend calls "generate" — same as "draft"
@app.post("/api/agents/content/generate/{content_id}")
async def generate_content(content_id: int):
    return await draft_content(content_id)


@app.post("/api/content/{content_id}/publish")
async def publish_content(content_id: int):
    """Publish content to connected platforms via the Publisher Agent."""
    with db_cursor() as conn:
        content = conn.execute("SELECT * FROM content_items WHERE id = ?", (content_id,)).fetchone()
        if not content:
            raise HTTPException(404, "Content not found")
        content = dict(content)
        creator_id = content["creator_id"]

    # Update status to publishing
    with db_cursor() as conn:
        conn.execute("UPDATE content_items SET status = 'publishing', updated_at = datetime('now') WHERE id = ?", (content_id,))

    # Trigger the publisher agent to actually post to connected platforms
    try:
        from agent_team import run_agent_by_name
        platform = content.get("platform", "instagram")
        draft = content.get("draft", content.get("brief", ""))
        title = content.get("title", "Content")

        # Run publisher agent
        result = await run_agent_by_name(
            "publisher_agent",
            f"Publish the following content to {platform}. Title: {title}. Content: {draft[:500]}. "
            f"Use the appropriate platform tool to post this. If the platform is not connected, report that.",
            creator_id, entity_type="content", entity_id=content_id
        )

        # Update status based on result
        summary = result.get("summary", "Published")
        with db_cursor() as conn:
            conn.execute("UPDATE content_items SET status = 'published', updated_at = datetime('now') WHERE id = ?", (content_id,))

        return {"status": "published", "content_id": content_id, "agent_result": summary}
    except Exception as e:
        with db_cursor() as conn:
            conn.execute("UPDATE content_items SET status = 'draft_ready', updated_at = datetime('now') WHERE id = ?", (content_id,))
        return {"status": "error", "error": str(e)}

@app.delete("/api/content/{content_id}")
async def delete_content(content_id: int):
    with db_cursor() as conn:
        conn.execute("DELETE FROM content_items WHERE id = ?", (content_id,))
        conn.execute("DELETE FROM approval_queue WHERE entity_type = 'content' AND entity_id = ?", (content_id,))
        return {"status": "deleted"}


# ─── Invoices / Finance ───

@app.get("/api/invoices")
async def get_invoices(status: Optional[str] = None):
    with db_cursor() as conn:
        if status:
            rows = conn.execute("SELECT * FROM invoices WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM invoices ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

@app.post("/api/invoices")
async def add_invoice(data: dict):
    with db_cursor() as conn:
        creator = conn.execute("SELECT id FROM creators LIMIT 1").fetchone()
        if not creator:
            raise HTTPException(404, "No creator")
        cur = conn.execute("""
            INSERT INTO invoices (creator_id, deal_id, client_name, amount, status)
            VALUES (?, ?, ?, ?, 'draft')
        """, (creator["id"], data.get("deal_id"), data.get("client_name", ""),
              data.get("amount", 0)))
        return {"id": cur.lastrowid, "status": "created"}

@app.post("/api/agents/finance/invoice/{invoice_id}")
async def generate_invoice(invoice_id: int):
    creator = None
    with db_cursor() as conn:
        creator = conn.execute("SELECT id FROM creators LIMIT 1").fetchone()
    if not creator:
        raise HTTPException(404, "No creator")
    result = await finance_agent_invoice(creator["id"], invoice_id)
    return result

@app.post("/api/invoices/{invoice_id}/mark-paid")
async def mark_invoice_paid(invoice_id: int):
    with db_cursor() as conn:
        conn.execute("""
            UPDATE invoices SET status = 'paid', paid_at = datetime('now')
            WHERE id = ?
        """, (invoice_id,))
        # Update creator's cleared revenue
        inv = conn.execute("SELECT amount, creator_id FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if inv:
            conn.execute("UPDATE creators SET cleared_revenue = cleared_revenue + ? WHERE id = ?",
                         (inv["amount"], inv["creator_id"]))
        return {"status": "paid"}


# ─── Approval Gates ───

@app.get("/api/approvals")
async def get_approvals(status: Optional[str] = None):
    with db_cursor() as conn:
        if status:
            rows = conn.execute("SELECT * FROM approval_queue WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM approval_queue ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

@app.post("/api/approvals/{approval_id}/resolve")
async def resolve_approval_gate(approval_id: int, decision: str = Query(...)):
    if decision not in ("approved", "declined"):
        raise HTTPException(400, "Decision must be 'approved' or 'declined'")
    return await resolve_approval(approval_id, decision)


# ─── Agent Activity Feed ───

@app.get("/api/activities")
async def get_activities(limit: int = 50):
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_activities ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

@app.get("/api/agents/status")
async def agent_status():
    """Get status of all 4 agents."""
    with db_cursor() as conn:
        agents = {}
        for name, display in [
            ("deal_agent", "Deal Agent"), ("content_agent", "Content Agent"),
            ("finance_agent", "Finance Agent"), ("memory_agent", "Memory Agent")
        ]:
            last = conn.execute(
                "SELECT * FROM agent_activities WHERE agent_name = ? ORDER BY created_at DESC LIMIT 1",
                (name,)
            ).fetchone()
            count = conn.execute(
                "SELECT COUNT(*) FROM agent_activities WHERE agent_name = ?", (name,)
            ).fetchone()[0]
            agents[name] = {
                "name": display,
                "total_actions": count,
                "last_action": dict(last) if last else None,
                "status": "active",
            }
        return agents


# ─── Memory / Patterns ───

@app.get("/api/memory")
async def get_memory():
    with db_cursor() as conn:
        rows = conn.execute("SELECT * FROM memory_patterns ORDER BY confidence DESC").fetchall()
        return [dict(r) for r in rows]

@app.post("/api/agents/memory/learn")
async def learn_patterns():
    creator = None
    with db_cursor() as conn:
        creator = conn.execute("SELECT id FROM creators LIMIT 1").fetchone()
    if not creator:
        raise HTTPException(404, "No creator")
    result = await memory_agent_learn(creator["id"])
    return result


# ─── System ───

@app.get("/api/system/status")
async def system_status():
    providers = get_provider_status()
    active = get_active_provider()
    return {
        "name": "CreatorForge OS",
        "version": "2.0.0",
        "tagline": "The Agentic Operating System for Creators",
        "llm_enabled": True,
        "active_provider": active,
        "providers": providers,
        "agents": ["deal_agent", "content_agent", "finance_agent", "memory_agent"],
        "features": [
            "Multi-agent orchestration with live activity feed",
            "Human-in-the-loop approval gates",
            "Performance memory & pattern learning",
            "Brand-creator fit scoring & negotiation",
            "Content drafting & platform optimization",
            "Invoice generation & payment tracking",
            "Storefront with real-time sales data",
            "Multi-provider LLM with automatic failover",
        ],
    }


# ─── Onboarding ───

class OnboardRequest(BaseModel):
    company_name: str
    handle: str
    industry: str
    bio: str
    followers: int = 0
    monthly_revenue: float = 0

@app.post("/api/onboard")
async def onboard(req: OnboardRequest):
    """Onboard a new company/creator. Wipes existing data and starts fresh."""
    import sqlite3
    # Delete existing data
    with db_cursor() as conn:
        for table in ["agent_thinking", "agent_activities", "approval_queue",
                       "memory_patterns", "invoices", "content_items", "deals",
                       "products", "documents", "creators"]:
            conn.execute(f"DELETE FROM {table}")
        # Reset auto-increment
        conn.execute("DELETE FROM sqlite_sequence")

        # Insert new creator
        avatar_map = {
            "music": "🎵", "tech": "💻", "fitness": "💪", "beauty": "💄",
            "food": "🍔", "fashion": "👗", "gaming": "🎮", "travel": "✈️",
            "education": "📚", "business": "💼", "lifestyle": "🌟", "health": "🏥",
        }
        avatar = avatar_map.get(req.industry.lower(), "🚀")
        conn.execute("""
            INSERT INTO creators (name, handle, bio, niche, followers, monthly_revenue, cleared_revenue, avatar)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """, (req.company_name, req.handle, req.bio, req.industry,
              req.followers, req.monthly_revenue, avatar))
        creator_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Log onboarding activity
        onboard_summary = f"🎉 {req.company_name} onboarded! Industry: {req.industry}, {req.followers:,} followers. All 4 agents are ready to work."
        conn.execute(
            "INSERT INTO agent_activities (agent_name, action, summary, status) VALUES ('system', 'onboard', ?, 'completed')",
            (onboard_summary,)
        )

    return {
        "status": "onboarded",
        "creator_id": creator_id,
        "message": f"Welcome {req.company_name}! Your workspace is ready. Add deals and content to see the agents in action."
    }


@app.post("/api/reset")
async def reset_workspace():
    """Reset everything — go back to onboarding screen."""
    with db_cursor() as conn:
        for table in ["agent_thinking", "agent_activities", "approval_queue",
                       "memory_patterns", "invoices", "content_items", "deals",
                       "products", "documents", "creators"]:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence")
    return {"status": "reset"}


# ─── Documents ───

@app.get("/api/documents")
async def get_documents(entity_type: Optional[str] = None, entity_id: Optional[int] = None):
    """Get all documents, optionally filtered by entity."""
    with db_cursor() as conn:
        if entity_type and entity_id:
            rows = conn.execute(
                "SELECT * FROM documents WHERE related_entity_type = ? AND related_entity_id = ? ORDER BY created_at DESC",
                (entity_type, entity_id)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: int):
    """Get a specific document."""
    with db_cursor() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Document not found")
        return dict(row)


@app.get("/api/thinking/recent")
async def get_recent_thinking(limit: int = 20):
    """Get recent thinking steps across all agents."""
    with db_cursor() as conn:
        rows = conn.execute(
            """SELECT t.*, a.summary as activity_summary
               FROM agent_thinking t
               LEFT JOIN agent_activities a ON t.activity_id = a.id
               ORDER BY t.created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


@app.get("/api/thinking/activity/{activity_id}")
async def get_thinking(activity_id: int):
    """Get the step-by-step thinking process for an agent activity."""
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_thinking WHERE activity_id = ? ORDER BY step_number",
            (activity_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ─── LLM Provider Management ───

class ProviderKeyRequest(BaseModel):
    provider: str
    api_key: str

@app.get("/api/llm/providers")
async def llm_providers():
    """Get status of all LLM providers."""
    return {
        "providers": get_provider_status(),
        "active_provider": get_active_provider(),
    }

@app.post("/api/llm/providers/key")
async def add_key(req: ProviderKeyRequest):
    """Add or update a provider API key."""
    result = add_provider_key(req.provider, req.api_key)
    return result

@app.delete("/api/llm/providers/{provider}")
async def remove_key(provider: str):
    """Remove a provider's API key."""
    result = remove_provider_key(provider)
    return result

@app.post("/api/llm/providers/reload")
async def reload_keys():
    """Reload provider configuration."""
    reload_providers()
    return {"status": "reloaded", "providers": get_provider_status()}


# ═══════════════════════════════════════════════════════════════
#  v3.0 — PLATFORM CONNECTORS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/platforms")
async def get_platforms():
    """Get all platform connectors and their connection status."""
    import platform_connectors as pc
    return {"platforms": pc.get_connector_status()}


@app.get("/api/platforms/info")
async def get_platforms_info():
    """Get info about all available platform connectors."""
    return {"connectors": pc.CONNECTOR_INFO}


class PlatformConnectRequest(BaseModel):
    platform: str
    credentials: dict


@app.post("/api/platforms/connect")
async def connect_platform(req: PlatformConnectRequest):
    """Connect a platform with credentials."""
    import platform_connectors as pc
    if req.platform not in pc.CONNECTOR_INFO:
        raise HTTPException(400, f"Unknown platform: {req.platform}")
    
    # Validate required fields
    info = pc.CONNECTOR_INFO[req.platform]
    for field in info["credential_fields"]:
        if field not in req.credentials:
            raise HTTPException(400, f"Missing required field: {field}")
    
    pc.store_platform_credential(req.platform, req.credentials)
    return {"status": "connected", "platform": req.platform}


@app.post("/api/platforms/{platform}/disconnect")
async def disconnect_platform(platform: str):
    """Disconnect a platform."""
    import platform_connectors as pc
    pc.disconnect_platform(platform)
    return {"status": "disconnected", "platform": platform}


@app.get("/api/platforms/actions")
async def get_platform_actions(limit: int = 50):
    """Get recent platform actions (audit trail)."""
    import platform_connectors as pc
    return {"actions": pc.get_platform_actions(limit)}


# ═══════════════════════════════════════════════════════════════
#  v3.0 — AGENT TEAM (12 agents)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/agents/team")
async def get_agent_team():
    """Get the full agent team status."""
    from agent_team import get_agent_team_status, AGENT_REGISTRY
    return {
        "agents": get_agent_team_status(),
        "total_agents": len(AGENT_REGISTRY),
        "expert_count": sum(1 for a in AGENT_REGISTRY.values() if a["type"] == "expert"),
        "worker_count": sum(1 for a in AGENT_REGISTRY.values() if a["type"] == "worker"),
    }


@app.post("/api/agents/{agent_name}/run")
async def run_agent_endpoint(agent_name: str, task: str = ""):
    """Run any agent by name with a custom task."""
    from agent_team import run_agent_by_name
    if not task:
        task = f"Run your standard analysis for the creator."
    result = await run_agent_by_name(agent_name, task)
    return result


# ═══════════════════════════════════════════════════════════════
#  v3.0 — AUTONOMOUS PIPELINE
# ═══════════════════════════════════════════════════════════════

@app.post("/api/agents/autopilot")
async def run_autopilot():
    """Run the full autonomous pipeline — all agents work together."""
    from agent_team import run_autonomous_pipeline
    result = await run_autonomous_pipeline()
    return result


@app.post("/api/agents/process-tasks")
async def process_agent_tasks():
    """Process all pending agent-to-agent tasks."""
    from agent_team import process_pending_agent_tasks
    result = await process_pending_agent_tasks()
    return result


@app.get("/api/agents/tasks")
async def get_agent_tasks():
    """Get all agent-to-agent tasks."""
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_tasks ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        return {"tasks": [dict(r) for r in rows]}


@app.get("/api/agents/schedules")
async def get_agent_schedules():
    """Get all agent schedules."""
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_schedules ORDER BY created_at DESC"
        ).fetchall()
        return {"schedules": [dict(r) for r in rows]}


class ScheduleRequest(BaseModel):
    agent_name: str
    schedule: str  # cron expression
    task: str


@app.post("/api/agents/schedules")
async def create_schedule(req: ScheduleRequest):
    """Create an agent schedule."""
    with db_cursor() as conn:
        conn.execute("""
            INSERT INTO agent_schedules (agent_name, schedule, task, enabled)
            VALUES (?, ?, ?, 1)
        """, (req.agent_name, req.schedule, req.task))
    return {"status": "created"}


@app.delete("/api/agents/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int):
    """Delete an agent schedule."""
    with db_cursor() as conn:
        conn.execute("DELETE FROM agent_schedules WHERE id = ?", (schedule_id,))
    return {"status": "deleted"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
