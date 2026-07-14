"""
CreatorForge OS — Data Models & SQLite Schema
"""
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from pydantic import BaseModel, Field
from typing import Optional

DB_PATH = os.environ.get("CREATORFORGE_DB", str(Path(__file__).parent / "creatorforge.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def db_cursor():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS creators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        handle TEXT NOT NULL UNIQUE,
        bio TEXT,
        niche TEXT,
        followers INTEGER DEFAULT 0,
        monthly_revenue REAL DEFAULT 0,
        cleared_revenue REAL DEFAULT 0,
        avatar TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER NOT NULL REFERENCES creators(id),
        title TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        sales_count INTEGER DEFAULT 0,
        category TEXT,
        image_emoji TEXT DEFAULT '📦',
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS deals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER NOT NULL REFERENCES creators(id),
        brand_name TEXT NOT NULL,
        brand_type TEXT,
        deal_type TEXT,
        offer_amount REAL,
        description TEXT,
        status TEXT DEFAULT 'pending_analysis',
        -- pending_analysis | analyzed | approved | declined | negotiating | closed
        fit_score REAL,
        fit_reasoning TEXT,
        negotiated_amount REAL,
        negotiated_terms TEXT,
        agent_analysis TEXT,
        needs_approval INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        closed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS content_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER NOT NULL REFERENCES creators(id),
        title TEXT NOT NULL,
        content_type TEXT DEFAULT 'post',
        -- post | video | story | reel
        brief TEXT,
        draft TEXT,
        status TEXT DEFAULT 'brief',
        -- brief | drafting | draft_ready | approved | published | declined
        platform TEXT DEFAULT 'instagram',
        agent_reasoning TEXT,
        needs_approval INTEGER DEFAULT 1,
        scheduled_for TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        published_at TEXT
    );

    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER NOT NULL REFERENCES creators(id),
        deal_id INTEGER REFERENCES deals(id),
        client_name TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'draft',
        -- draft | pending_approval | approved | sent | paid
        items TEXT, -- JSON array
        agent_notes TEXT,
        needs_approval INTEGER DEFAULT 1,
        due_date TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        paid_at TEXT
    );

    CREATE TABLE IF NOT EXISTS agent_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        -- deal_agent | content_agent | finance_agent | memory_agent
        action TEXT NOT NULL,
        entity_type TEXT,
        entity_id INTEGER,
        summary TEXT NOT NULL,
        details TEXT, -- JSON
        status TEXT DEFAULT 'completed',
        -- started | completed | awaiting_approval | approved | declined
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS memory_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER NOT NULL REFERENCES creators(id),
        pattern_type TEXT NOT NULL,
        -- deal_acceptance | deal_revenue | content_performance | brand_fit
        pattern_key TEXT NOT NULL,
        pattern_value TEXT NOT NULL,
        confidence REAL DEFAULT 0.5,
        sample_count INTEGER DEFAULT 1,
        insight TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS approval_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        -- deal | content | invoice
        entity_id INTEGER NOT NULL,
        agent_name TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        -- pending | approved | declined
        created_at TEXT DEFAULT (datetime('now')),
        resolved_at TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_deals_creator ON deals(creator_id);
    CREATE INDEX IF NOT EXISTS idx_content_creator ON content_items(creator_id);
    CREATE INDEX IF NOT EXISTS idx_activities_created ON agent_activities(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_queue(status);

    CREATE TABLE IF NOT EXISTS agent_thinking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_id INTEGER,
        agent_name TEXT NOT NULL,
        step_number INTEGER NOT NULL,
        phase TEXT NOT NULL,
        thought TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_thinking_activity ON agent_thinking(activity_id);
    """)
    conn.commit()
    conn.close()


# ── Pydantic Schemas ──

class Creator(BaseModel):
    id: Optional[int] = None
    name: str
    handle: str
    bio: Optional[str] = None
    niche: Optional[str] = None
    followers: int = 0
    monthly_revenue: float = 0
    cleared_revenue: float = 0
    avatar: Optional[str] = None

class Product(BaseModel):
    id: Optional[int] = None
    creator_id: int
    title: str
    description: Optional[str] = None
    price: float
    sales_count: int = 0
    category: Optional[str] = None
    image_emoji: str = "📦"

class Deal(BaseModel):
    id: Optional[int] = None
    creator_id: int
    brand_name: str
    brand_type: Optional[str] = None
    deal_type: Optional[str] = None
    offer_amount: Optional[float] = None
    description: Optional[str] = None
    status: str = "pending_analysis"
    fit_score: Optional[float] = None
    fit_reasoning: Optional[str] = None
    negotiated_amount: Optional[float] = None
    negotiated_terms: Optional[str] = None
    agent_analysis: Optional[str] = None
    needs_approval: int = 1

class ContentItem(BaseModel):
    id: Optional[int] = None
    creator_id: int
    title: str
    content_type: str = "post"
    brief: Optional[str] = None
    draft: Optional[str] = None
    status: str = "brief"
    platform: str = "instagram"
    agent_reasoning: Optional[str] = None
    needs_approval: int = 1
    scheduled_for: Optional[str] = None

class Invoice(BaseModel):
    id: Optional[int] = None
    creator_id: int
    deal_id: Optional[int] = None
    client_name: str
    amount: float
    status: str = "draft"
    items: Optional[str] = None
    agent_notes: Optional[str] = None
    needs_approval: int = 1
    due_date: Optional[str] = None

class AgentActivity(BaseModel):
    id: Optional[int] = None
    agent_name: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    summary: str
    details: Optional[str] = None
    status: str = "completed"

class MemoryPattern(BaseModel):
    id: Optional[int] = None
    creator_id: int
    pattern_type: str
    pattern_key: str
    pattern_value: str
    confidence: float = 0.5
    sample_count: int = 1
    insight: Optional[str] = None

class ApprovalItem(BaseModel):
    id: Optional[int] = None
    entity_type: str
    entity_id: int
    agent_name: str
    title: str
    summary: str
    status: str = "pending"
