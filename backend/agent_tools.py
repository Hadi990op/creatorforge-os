"""
CreatorForge OS — Agent Tools Library
======================================
Real tools that agents can call during a ReAct loop.
Each tool takes arguments, executes a real action, and returns results.

Tools available:
  - web_search(query)           → Search the web for real-time info
  - web_fetch(url)              → Fetch and extract text from a URL
  - youtube_search(query)       → Search YouTube for videos
  - trend_research(topic)       → Research trending topics in a niche
  - competitor_analysis(brand)  → Analyze a brand's online presence
  - market_rate_research(niche, followers, deal_type) → Get real market rates
  - generate_pdf(title, content) → Generate a PDF document
  - draft_email(to, subject, body) → Draft an email
  - create_content_calendar(items) → Create a content schedule
  - generate_invoice(deal_id)   → Generate an invoice from a deal
  - db_query(table, filters)    → Query the database
  - calculate_tax(revenue)      → Calculate tax estimates
"""
import os
import json
import time
import asyncio
import re
import hashlib
from typing import Optional
from datetime import datetime, timedelta

import httpx

# ═══════════════════════════════════════════════════════════════
#  Tool Registry
# ═══════════════════════════════════════════════════════════════

TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "Search the web for real-time information about any topic. Returns search results with titles, URLs, and snippets.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "web_fetch",
        "description": "Fetch the full text content of a web page. Use this to read brand websites, articles, or any URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "youtube_search",
        "description": "Search YouTube for videos. Returns video titles, channel names, view counts, and publish dates.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "YouTube search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "trend_research",
        "description": "Research trending topics in a creator's niche. Returns current trends, popular content formats, and emerging topics.",
        "parameters": {
            "type": "object",
            "properties": {
                "niche": {"type": "string", "description": "The creator's niche (e.g., music, tech, fitness)"},
                "platform": {"type": "string", "description": "Platform to research (youtube, tiktok, instagram, all)"}
            },
            "required": ["niche"]
        }
    },
    {
        "name": "competitor_analysis",
        "description": "Analyze a brand's online presence by searching for their website, social media, recent news, and reputation.",
        "parameters": {
            "type": "object",
            "properties": {
                "brand_name": {"type": "string", "description": "Name of the brand to analyze"},
                "creator_niche": {"type": "string", "description": "The creator's niche for relevance comparison"}
            },
            "required": ["brand_name"]
        }
    },
    {
        "name": "market_rate_research",
        "description": "Research current market rates for brand deals based on creator's follower count and niche. Returns real benchmark data.",
        "parameters": {
            "type": "object",
            "properties": {
                "niche": {"type": "string", "description": "Creator's niche"},
                "followers": {"type": "integer", "description": "Creator's follower count"},
                "deal_type": {"type": "string", "description": "Type of deal (sponsorship, collab, affiliate)"}
            },
            "required": ["niche", "followers"]
        }
    },
    {
        "name": "generate_document",
        "description": "Generate a formatted document (contract, proposal, invoice, content brief) and save it as a file. Returns the document path.",
        "parameters": {
            "type": "object",
            "properties": {
                "doc_type": {"type": "string", "description": "Type: contract, proposal, invoice, brief, report, email"},
                "title": {"type": "string", "description": "Document title"},
                "content": {"type": "string", "description": "Full document content in plain text"},
                "related_entity_type": {"type": "string", "description": "deal, content, invoice, or none"},
                "related_entity_id": {"type": "integer", "description": "ID of related entity"}
            },
            "required": ["doc_type", "title", "content"]
        }
    },
    {
        "name": "create_content_calendar",
        "description": "Create a content calendar with scheduled posts. Each item has a date, platform, title, and content type.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "YYYY-MM-DD format"},
                            "platform": {"type": "string"},
                            "title": {"type": "string"},
                            "content_type": {"type": "string"}
                        }
                    },
                    "description": "Content calendar items"
                }
            },
            "required": ["items"]
        }
    },
    {
        "name": "db_lookup",
        "description": "Look up data from the CreatorForge database. Query past deals, content items, memory patterns, or creator stats.",
        "parameters": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Table: deals, content_items, memory_patterns, products, invoices, agent_activities"},
                "filter": {"type": "string", "description": "Optional filter condition (e.g., 'status=approved')"}
            },
            "required": ["table"]
        }
    },
    {
        "name": "create_content_item",
        "description": "Create a new content item in the content pipeline. Use this when a deal is approved and content needs to be produced.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content_type": {"type": "string", "description": "post, video, reel, story, carousel"},
                "brief": {"type": "string", "description": "Content brief / description"},
                "platform": {"type": "string", "description": "instagram, youtube, tiktok, twitter, linkedin"}
            },
            "required": ["title", "content_type", "brief", "platform"]
        }
    },
    {
        "name": "create_invoice",
        "description": "Create an invoice in the system. Use this when a deal is approved to automatically generate billing.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string"},
                "amount": {"type": "number"},
                "deal_id": {"type": "integer"},
                "notes": {"type": "string"}
            },
            "required": ["client_name", "amount"]
        }
    },
    {
        "name": "store_memory",
        "description": "Store a learned pattern or insight in the memory system for future use by other agents.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern_type": {"type": "string", "description": "deal_acceptance, deal_revenue, content_performance, brand_fit, market_trend"},
                "pattern_key": {"type": "string", "description": "Key identifier for the pattern"},
                "pattern_value": {"type": "string", "description": "The pattern value"},
                "insight": {"type": "string", "description": "Human-readable insight"},
                "confidence": {"type": "number", "description": "Confidence 0.0-1.0"}
            },
            "required": ["pattern_type", "pattern_key", "pattern_value", "insight"]
        }
    },
    {
        "name": "instagram_post",
        "description": "Post content to Instagram (photo, reel, or story). Requires Instagram to be connected.",
        "parameters": {
            "type": "object",
            "properties": {
                "media_type": {"type": "string", "description": "photo, reel, or story"},
                "media_path": {"type": "string", "description": "Path to the media file (image or video)"},
                "caption": {"type": "string", "description": "Caption for the post (for photo/reel)"}
            },
            "required": ["media_type", "media_path"]
        }
    },
    {
        "name": "instagram_dm",
        "description": "Send a direct message to an Instagram user. Requires Instagram to be connected.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Instagram username to send DM to"},
                "message": {"type": "string", "description": "Message text"}
            },
            "required": ["username", "message"]
        }
    },
    {
        "name": "instagram_insights",
        "description": "Get Instagram analytics and insights. Requires Instagram to be connected.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "youtube_upload",
        "description": "Upload a video to YouTube. Requires YouTube to be connected.",
        "parameters": {
            "type": "object",
            "properties": {
                "video_path": {"type": "string", "description": "Path to the video file"},
                "title": {"type": "string", "description": "Video title"},
                "description": {"type": "string", "description": "Video description"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Video tags"},
                "privacy": {"type": "string", "description": "public, unlisted, or private (default: public)"}
            },
            "required": ["video_path", "title", "description"]
        }
    },
    {
        "name": "youtube_analytics",
        "description": "Get YouTube channel analytics (subscribers, views, video count). Requires YouTube to be connected.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "send_email",
        "description": "Send a real email to someone. Requires email (SMTP) to be connected.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body (plain text)"},
                "html": {"type": "boolean", "description": "Whether body is HTML (default: false)"},
                "cc": {"type": "string", "description": "CC recipients (comma-separated)"},
                "attachments": {"type": "array", "items": {"type": "string"}, "description": "File paths to attach"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "stripe_invoice",
        "description": "Create and send a real Stripe invoice. Requires Stripe to be connected.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_email": {"type": "string", "description": "Customer's email address"},
                "amount": {"type": "number", "description": "Invoice amount in dollars"},
                "currency": {"type": "string", "description": "Currency code (default: usd)"},
                "description": {"type": "string", "description": "Invoice description"}
            },
            "required": ["customer_email", "amount", "description"]
        }
    },
    {
        "name": "stripe_payment_link",
        "description": "Create a Stripe payment link for a product. Requires Stripe to be connected.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Price in dollars"},
                "product_name": {"type": "string", "description": "Product name"},
                "currency": {"type": "string", "description": "Currency code (default: usd)"}
            },
            "required": ["amount", "product_name"]
        }
    },
    {
        "name": "twitter_post",
        "description": "Post a tweet. Requires Twitter/X to be connected.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Tweet text (max 280 characters)"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "twitter_thread",
        "description": "Post a Twitter thread (multiple tweets). Requires Twitter/X to be connected.",
        "parameters": {
            "type": "object",
            "properties": {
                "tweets": {"type": "array", "items": {"type": "string"}, "description": "List of tweet texts"}
            },
            "required": ["tweets"]
        }
    },
    {
        "name": "send_notification",
        "description": "Send a notification via Slack, Discord, or Telegram. Requires the platform to be connected.",
        "parameters": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "slack, discord, or telegram"},
                "message": {"type": "string", "description": "Notification message"},
                "channel": {"type": "string", "description": "Channel (for Slack) or chat_id (for Telegram)"},
                "webhook_url": {"type": "string", "description": "Discord webhook URL (for Discord)"}
            },
            "required": ["platform", "message"]
        }
    },
    {
        "name": "create_calendar_event",
        "description": "Create a calendar event (.ics file) for scheduling.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title"},
                "start_time": {"type": "string", "description": "Start time (ISO format: 2026-01-15T14:00:00)"},
                "end_time": {"type": "string", "description": "End time (ISO format, optional)"},
                "description": {"type": "string", "description": "Event description"},
                "location": {"type": "string", "description": "Event location"}
            },
            "required": ["title", "start_time"]
        }
    },
    {
        "name": "github_issue",
        "description": "Create a GitHub issue. Requires GitHub to be connected.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository name (owner/repo format)"},
                "title": {"type": "string", "description": "Issue title"},
                "body": {"type": "string", "description": "Issue body (Markdown)"},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "Issue labels"}
            },
            "required": ["repo", "title", "body"]
        }
    },
    {
        "name": "delegate_to_agent",
        "description": "Delegate a task to another agent. The other agent will execute it asynchronously.",
        "parameters": {
            "type": "object",
            "properties": {
                "to_agent": {"type": "string", "description": "Agent name: deal_agent, content_agent, finance_agent, memory_agent, strategy_agent, outreach_agent, analytics_agent, scheduler_agent, publisher_agent, email_agent, contract_agent, notification_agent"},
                "task": {"type": "string", "description": "Task description for the other agent"},
                "priority": {"type": "integer", "description": "Priority 1-10 (1=highest, default: 5)"}
            },
            "required": ["to_agent", "task"]
        }
    },
    {
        "name": "check_platform_status",
        "description": "Check which platforms are connected and available for actions.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "finish",
        "description": "Signal that the agent has completed its task. Provide a summary of what was accomplished.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Summary of what the agent accomplished"},
                "result": {"type": "object", "description": "Structured result data"}
            },
            "required": ["summary"]
        }
    }
]


# ═══════════════════════════════════════════════════════════════
#  Tool Implementations
# ═══════════════════════════════════════════════════════════════

async def execute_tool(tool_name: str, arguments: dict, creator_id: int = 1) -> dict:
    """Execute a tool by name with given arguments. Returns result dict."""
    try:
        if tool_name == "web_search":
            return await _web_search(arguments["query"])
        elif tool_name == "web_fetch":
            return await _web_fetch(arguments["url"])
        elif tool_name == "youtube_search":
            return await _youtube_search(arguments["query"])
        elif tool_name == "trend_research":
            return await _trend_research(arguments.get("niche", "general"), arguments.get("platform", "all"))
        elif tool_name == "competitor_analysis":
            return await _competitor_analysis(arguments["brand_name"], arguments.get("creator_niche", ""))
        elif tool_name == "market_rate_research":
            return await _market_rate_research(arguments["niche"], arguments["followers"], arguments.get("deal_type", "sponsorship"))
        elif tool_name == "generate_document":
            return _generate_document(
                arguments["doc_type"], arguments["title"], arguments["content"],
                arguments.get("related_entity_type"), arguments.get("related_entity_id"),
                creator_id
            )
        elif tool_name == "create_content_calendar":
            return _create_content_calendar(arguments["items"], creator_id)
        elif tool_name == "db_lookup":
            return _db_lookup(arguments["table"], arguments.get("filter"), creator_id)
        elif tool_name == "create_content_item":
            return _create_content_item(arguments, creator_id)
        elif tool_name == "create_invoice":
            return _create_invoice(arguments, creator_id)
        elif tool_name == "store_memory":
            return _store_memory(arguments, creator_id)
        elif tool_name == "instagram_post":
            import platform_connectors as pc
            media_type = arguments["media_type"]
            if media_type == "photo":
                return pc.instagram_post_photo(arguments["media_path"], arguments.get("caption", ""), agent_name="content_agent")
            elif media_type == "reel":
                return pc.instagram_post_reel(arguments["media_path"], arguments.get("caption", ""), agent_name="content_agent")
            elif media_type == "story":
                return pc.instagram_post_story(arguments["media_path"], agent_name="content_agent")
            return {"error": f"Unknown media type: {media_type}"}
        elif tool_name == "instagram_dm":
            import platform_connectors as pc
            return pc.instagram_send_dm(arguments["username"], arguments["message"], agent_name="deal_agent")
        elif tool_name == "instagram_insights":
            import platform_connectors as pc
            return pc.instagram_get_insights(agent_name="analytics_agent")
        elif tool_name == "youtube_upload":
            import platform_connectors as pc
            return pc.youtube_upload_video(
                arguments["video_path"], arguments["title"], arguments["description"],
                arguments.get("tags", []), arguments.get("privacy", "public"), agent_name="content_agent"
            )
        elif tool_name == "youtube_analytics":
            import platform_connectors as pc
            return pc.youtube_get_analytics(agent_name="analytics_agent")
        elif tool_name == "send_email":
            import platform_connectors as pc
            return pc.send_email(
                arguments["to"], arguments["subject"], arguments["body"],
                arguments.get("html", False), arguments.get("attachments"),
                arguments.get("cc"), agent_name="email_agent"
            )
        elif tool_name == "stripe_invoice":
            import platform_connectors as pc
            return pc.stripe_create_invoice(
                arguments["customer_email"], arguments["amount"],
                arguments.get("currency", "usd"), arguments["description"], agent_name="finance_agent"
            )
        elif tool_name == "stripe_payment_link":
            import platform_connectors as pc
            return pc.stripe_create_payment_link(
                arguments["amount"], arguments.get("currency", "usd"),
                arguments["product_name"], agent_name="finance_agent"
            )
        elif tool_name == "twitter_post":
            import platform_connectors as pc
            return pc.twitter_post_tweet(arguments["text"], agent_name="content_agent")
        elif tool_name == "twitter_thread":
            import platform_connectors as pc
            return pc.twitter_post_thread(arguments["tweets"], agent_name="content_agent")
        elif tool_name == "send_notification":
            import platform_connectors as pc
            platform = arguments["platform"]
            message = arguments["message"]
            if platform == "slack":
                return pc.send_slack_notification(arguments.get("channel", "#general"), message, agent_name="notification_agent")
            elif platform == "discord":
                return pc.send_discord_notification(arguments.get("webhook_url", ""), message, agent_name="notification_agent")
            elif platform == "telegram":
                creds = pc.get_platform_credential("telegram")
                if creds:
                    return pc.send_telegram_notification(creds["bot_token"], arguments.get("channel", creds.get("chat_id", "")), message, agent_name="notification_agent")
                return {"error": "Telegram not connected"}
            return {"error": f"Unknown notification platform: {platform}"}
        elif tool_name == "create_calendar_event":
            import platform_connectors as pc
            return pc.create_calendar_event(
                arguments["title"], arguments["start_time"], arguments.get("end_time"),
                arguments.get("description", ""), arguments.get("location", ""), agent_name="scheduler_agent"
            )
        elif tool_name == "github_issue":
            import platform_connectors as pc
            return pc.github_create_issue(
                arguments["repo"], arguments["title"], arguments["body"],
                arguments.get("labels", []), agent_name="contract_agent"
            )
        elif tool_name == "delegate_to_agent":
            return _delegate_to_agent(arguments["to_agent"], arguments["task"],
                                      arguments.get("priority", 5), creator_id)
        elif tool_name == "check_platform_status":
            import platform_connectors as pc
            return {"platforms": pc.get_connector_status()}
        elif tool_name == "finish":
            return {"tool": "finish", "summary": arguments["summary"], "result": arguments.get("result", {})}
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        return {"error": f"Tool '{tool_name}' failed: {str(e)}"}


# ── Web Search (using DuckDuckGo Instant Answer API + HTML scraping) ──

async def _web_search(query: str) -> dict:
    """Search the web using multiple methods."""
    results = []
    
    # Method 1: Try DuckDuckGo Instant Answer API
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("AbstractText"):
                    results.append({
                        "title": data.get("Heading", query),
                        "url": data.get("AbstractURL", ""),
                        "snippet": data["AbstractText"][:300]
                    })
                for topic in data.get("RelatedTopics", [])[:5]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({
                            "title": topic.get("Text", "")[:80],
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", "")[:200]
                        })
    except Exception:
        pass
    
    # Method 2: Construct likely URLs and fetch them directly
    # This works because we can fetch real websites even if search APIs block us
    if len(results) < 3:
        # Try common URL patterns based on the query
        brand_words = query.lower().replace("app", "").replace("company", "").replace("products", "").strip()
        brand_slug = brand_words.split()[0] if brand_words.split() else ""
        
        candidate_urls = [
            f"https://www.{brand_slug}.com",
            f"https://{brand_slug}.com",
            f"https://www.{brand_slug}.io",
            f"https://{brand_slug}.io",
            f"https://www.{brand_slug}.ai",
        ]
        
        for url in candidate_urls:
            if len(results) >= 5:
                break
            try:
                async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                    resp = await client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    })
                    if resp.status_code == 200:
                        import re
                        title_match = re.search(r'<title[^>]*>([^<]+)</title>', resp.text, re.IGNORECASE)
                        title = title_match.group(1).strip() if title_match else url
                        text = re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=re.DOTALL)
                        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                        text = re.sub(r'<[^>]+>', ' ', text)
                        text = re.sub(r'\s+', ' ', text).strip()
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": text[:300]
                        })
            except Exception:
                continue
    
    # Method 3: Use the agent's web_search tool (LibertAI) via a subprocess call
    # This is a fallback that uses the agent's own search capability
    if len(results) < 2:
        try:
            import subprocess
            # Use the agent's web search via curl to LibertAI
            proc = subprocess.run(
                ["curl", "-s", "-X", "POST", "https://search.libertai.io/api/search",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps({"query": query, "count": 5})],
                capture_output=True, text=True, timeout=10
            )
            if proc.returncode == 0 and proc.stdout:
                data = json.loads(proc.stdout)
                for item in data.get("results", [])[:5]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", "")[:200]
                    })
        except Exception:
            pass
    
    return {"tool": "web_search", "query": query, "results": results[:8]}


# ── Web Fetch ──

async def _web_fetch(url: str) -> dict:
    """Fetch a URL and extract readable text content."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
            text = resp.text
        
        # Strip HTML tags
        import re
        # Remove scripts and styles
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        # Remove tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Get title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', resp.text, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else url
        
        return {
            "tool": "web_fetch",
            "url": url,
            "title": title,
            "content": text[:3000],  # Limit to 3000 chars
            "content_length": len(text)
        }
    except Exception as e:
        return {"tool": "web_fetch", "url": url, "error": str(e)}


# ── YouTube Search ──

async def _youtube_search(query: str) -> dict:
    """Search YouTube for videos using the public search page."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            # Use YouTube's search results page
            resp = await client.get(
                f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
            )
            text = resp.text
        
        # Extract video data from YouTube's JSON
        import re
        # YouTube embeds video data in a JSON script
        video_ids = re.findall(r'"videoId":"([^"]+)"', text)
        titles = re.findall(r'"title":{"runs":\[{"text":"([^"]+)"}\]', text)
        
        # Also try alternative pattern
        if not titles:
            titles = re.findall(r'"title":\s*"([^"]{10,})"', text)
        
        results = []
        seen = set()
        for i, vid in enumerate(video_ids):
            if vid not in seen and len(vid) == 11:
                seen.add(vid)
                title = titles[i] if i < len(titles) else f"Video {vid}"
                results.append({
                    "video_id": vid,
                    "title": title[:100],
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "thumbnail": f"https://img.youtube.com/vi/{vid}/mqdefault.jpg"
                })
            if len(results) >= 5:
                break
        
        return {"tool": "youtube_search", "query": query, "results": results}
    except Exception as e:
        return {"tool": "youtube_search", "query": query, "error": str(e), "results": []}


# ── Trend Research ──

async def _trend_research(niche: str, platform: str = "all") -> dict:
    """Research trending topics in a creator's niche."""
    queries = [
        f"{niche} content trends 2025 2026",
        f"popular {niche} content ideas",
    ]
    if platform != "all":
        queries.insert(0, f"{platform} {niche} trending")
    
    all_results = []
    for q in queries[:2]:
        search_result = await _web_search(q)
        all_results.extend(search_result.get("results", []))
    
    # Also search YouTube
    yt_result = await _youtube_search(f"{niche} trending 2025")
    yt_videos = yt_result.get("results", [])
    
    return {
        "tool": "trend_research",
        "niche": niche,
        "platform": platform,
        "web_results": all_results[:5],
        "youtube_trends": yt_videos[:3],
        "summary": f"Found {len(all_results)} web results and {len(yt_videos)} YouTube videos about {niche} trends."
    }


# ── Competitor / Brand Analysis ──

async def _competitor_analysis(brand_name: str, creator_niche: str = "") -> dict:
    """Analyze a brand's online presence."""
    # Search for the brand
    search_results = await _web_search(f"{brand_name} company products review")
    
    # Search for brand reputation
    rep_results = await _web_search(f"{brand_name} reputation controversy review")
    
    # Try to find their website
    website = None
    for r in search_results.get("results", []):
        url = r.get("url", "")
        if brand_name.lower().split()[0] in url.lower() and "duckduckgo" not in url:
            website = url
            break
    
    # If we found a website, fetch it
    website_content = None
    if website:
        fetch_result = await _web_fetch(website)
        website_content = fetch_result.get("content", "")[:1000] if not fetch_result.get("error") else None
    
    # Check social media presence
    social_search = await _web_search(f"{brand_name} instagram twitter youtube social media")
    
    return {
        "tool": "competitor_analysis",
        "brand_name": brand_name,
        "website": website,
        "website_summary": website_content,
        "search_results": search_results.get("results", [])[:4],
        "reputation_results": rep_results.get("results", [])[:3],
        "social_presence": social_search.get("results", [])[:3],
        "creator_niche": creator_niche,
        "analysis": f"Analyzed {brand_name}'s online presence. Found {len(search_results.get('results', []))} results about the brand, {len(rep_results.get('results', []))} reputation results."
    }


# ── Market Rate Research ──

async def _market_rate_research(niche: str, followers: int, deal_type: str = "sponsorship") -> dict:
    """Research current market rates for brand deals."""
    query = f"influencer {deal_type} rates {followers} followers {niche} 2025 pricing"
    results = await _web_search(query)
    
    # Also search for benchmarks
    benchmark_query = f"influencer marketing pricing benchmark {followers} followers"
    benchmark_results = await _web_search(benchmark_query)
    
    # Determine tier
    if followers < 10000:
        tier = "nano"
    elif followers < 50000:
        tier = "micro"
    elif followers < 200000:
        tier = "mid-tier"
    elif followers < 500000:
        tier = "macro"
    else:
        tier = "mega"
    
    return {
        "tool": "market_rate_research",
        "niche": niche,
        "followers": followers,
        "deal_type": deal_type,
        "tier": tier,
        "search_results": results.get("results", [])[:5],
        "benchmark_results": benchmark_results.get("results", [])[:3],
        "estimated_range": _get_rate_range(followers, deal_type)
    }


def _get_rate_range(followers: int, deal_type: str) -> dict:
    """Get estimated rate range based on follower count."""
    rates = {
        "nano": {"min": 50, "max": 250},
        "micro": {"min": 200, "max": 800},
        "mid-tier": {"min": 800, "max": 3000},
        "macro": {"min": 3000, "max": 8000},
        "mega": {"min": 8000, "max": 20000},
    }
    if followers < 10000:
        tier = "nano"
    elif followers < 50000:
        tier = "micro"
    elif followers < 200000:
        tier = "mid-tier"
    elif followers < 500000:
        tier = "macro"
    else:
        tier = "mega"
    
    return rates[tier]


# ── Document Generation ──

def _generate_document(doc_type: str, title: str, content: str,
                       related_entity_type: str = None, related_entity_id: int = None,
                       creator_id: int = 1) -> dict:
    """Generate a formatted document and save it."""
    # Create documents directory
    docs_dir = os.path.join(os.path.dirname(__file__), "documents")
    os.makedirs(docs_dir, exist_ok=True)
    
    # Generate filename
    safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{doc_type}_{safe_title}_{timestamp}.md"
    filepath = os.path.join(docs_dir, filename)
    
    # Format the document
    doc_content = f"""# {title}

**Document Type:** {doc_type.upper()}
**Generated:** {datetime.now().strftime("%B %d, %Y at %I:%M %p")}
**Generated by:** CreatorForge OS Agent

---

{content}

---

*This document was generated by CreatorForge OS — The Agentic Operating System for Creators*
"""
    
    with open(filepath, "w") as f:
        f.write(doc_content)
    
    # Save to database
    from models import db_cursor
    with db_cursor() as conn:
        conn.execute("""
            INSERT INTO documents (creator_id, doc_type, title, content, filename, 
                                   related_entity_type, related_entity_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (creator_id, doc_type, title, content, filename,
              related_entity_type, related_entity_id))
        doc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    return {
        "tool": "generate_document",
        "doc_type": doc_type,
        "title": title,
        "doc_id": doc_id,
        "filename": filename,
        "path": filepath,
        "preview": content[:200]
    }


# ── Content Calendar ──

def _create_content_calendar(items: list, creator_id: int = 1) -> dict:
    """Create content calendar items in the database."""
    from models import db_cursor
    created = []
    with db_cursor() as conn:
        for item in items:
            title = item.get("title", "Untitled")
            platform = item.get("platform", "instagram")
            content_type = item.get("content_type", "post")
            date = item.get("date", datetime.now().strftime("%Y-%m-%d"))
            
            cur = conn.execute("""
                INSERT INTO content_items (creator_id, title, content_type, brief, 
                                          platform, status, scheduled_for)
                VALUES (?, ?, ?, ?, ?, 'scheduled', ?)
            """, (creator_id, title, content_type, f"Scheduled for {date}",
                  platform, date))
            created.append({"id": cur.lastrowid, "title": title, "date": date, "platform": platform})
    
    return {
        "tool": "create_content_calendar",
        "created_count": len(created),
        "items": created
    }


# ── Database Lookup ──

def _db_lookup(table: str, filter_str: str = None, creator_id: int = 1) -> dict:
    """Look up data from the database."""
    from models import db_cursor
    
    allowed_tables = ["deals", "content_items", "memory_patterns", "products", 
                      "invoices", "agent_activities"]
    
    if table not in allowed_tables:
        return {"error": f"Table '{table}' not allowed. Use: {', '.join(allowed_tables)}"}
    
    with db_cursor() as conn:
        query = f"SELECT * FROM {table} WHERE creator_id = ? ORDER BY created_at DESC LIMIT 10"
        params = [creator_id]
        
        if filter_str:
            # Simple filter parsing: key=value
            if "=" in filter_str:
                key, val = filter_str.split("=", 1)
                query = f"SELECT * FROM {table} WHERE creator_id = ? AND {key} = ? ORDER BY created_at DESC LIMIT 10"
                params = [creator_id, val]
        
        rows = conn.execute(query, params).fetchall()
        results = [dict(r) for r in rows]
    
    return {"tool": "db_lookup", "table": table, "count": len(results), "results": results}


# ── Create Content Item ──

def _create_content_item(args: dict, creator_id: int = 1) -> dict:
    """Create a content item in the pipeline."""
    from models import db_cursor
    with db_cursor() as conn:
        cur = conn.execute("""
            INSERT INTO content_items (creator_id, title, content_type, brief, platform, status)
            VALUES (?, ?, ?, ?, ?, 'brief')
        """, (creator_id, args["title"], args.get("content_type", "post"),
              args.get("brief", ""), args.get("platform", "instagram")))
        content_id = cur.lastrowid
    
    return {"tool": "create_content_item", "content_id": content_id, "title": args["title"]}


# ── Create Invoice ──

def _create_invoice(args: dict, creator_id: int = 1) -> dict:
    """Create an invoice."""
    from models import db_cursor
    with db_cursor() as conn:
        cur = conn.execute("""
            INSERT INTO invoices (creator_id, deal_id, client_name, amount, status, agent_notes)
            VALUES (?, ?, ?, ?, 'draft', ?)
        """, (creator_id, args.get("deal_id"), args["client_name"],
              args["amount"], args.get("notes", "Auto-generated by Finance Agent")))
        invoice_id = cur.lastrowid
    
    return {"tool": "create_invoice", "invoice_id": invoice_id, "client_name": args["client_name"], "amount": args["amount"]}


# ── Store Memory ──

def _store_memory(args: dict, creator_id: int = 1) -> dict:
    """Store a memory pattern."""
    from models import db_cursor
    with db_cursor() as conn:
        # Check if pattern exists
        existing = conn.execute(
            "SELECT id, sample_count FROM memory_patterns WHERE creator_id = ? AND pattern_type = ? AND pattern_key = ?",
            (creator_id, args["pattern_type"], args["pattern_key"])
        ).fetchone()
        
        if existing:
            # Update existing pattern
            new_count = existing["sample_count"] + 1
            conn.execute("""
                UPDATE memory_patterns SET pattern_value = ?, insight = ?, confidence = ?,
                sample_count = ?, updated_at = datetime('now') WHERE id = ?
            """, (args["pattern_value"], args["insight"], args.get("confidence", 0.7),
                  new_count, existing["id"]))
            return {"tool": "store_memory", "updated": True, "pattern_id": existing["id"], "samples": new_count}
        else:
            cur = conn.execute("""
                INSERT INTO memory_patterns (creator_id, pattern_type, pattern_key, pattern_value, insight, confidence, sample_count)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (creator_id, args["pattern_type"], args["pattern_key"],
                  args["pattern_value"], args["insight"], args.get("confidence", 0.7)))
            return {"tool": "store_memory", "created": True, "pattern_id": cur.lastrowid}


# ═══════════════════════════════════════════════════════════════
#  Tool descriptions for LLM prompts
# ═══════════════════════════════════════════════════════════════

def get_tools_description() -> str:
    """Get a text description of all available tools for the LLM prompt."""
    lines = ["You have access to the following tools:"]
    for tool in TOOL_DEFINITIONS:
        params = tool["parameters"].get("properties", {})
        param_str = ", ".join(f'{k}: {v.get("description", k)}' for k, v in params.items())
        lines.append(f"\n- {tool['name']}({param_str}): {tool['description']}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  Agent-to-Agent Delegation
# ═══════════════════════════════════════════════════════════════

def _delegate_to_agent(to_agent: str, task: str, priority: int = 5, creator_id: int = 1) -> dict:
    """Delegate a task to another agent. Creates a task in the agent_tasks table."""
    with db_cursor() as conn:
        cur = conn.execute("""
            INSERT INTO agent_tasks (from_agent, to_agent, task, priority, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', datetime('now'))
        """, ("autonomous", to_agent, task, priority))
        task_id = cur.lastrowid
    
    # Log the delegation as an activity
    conn2 = get_db()
    conn2.execute("""
        INSERT INTO agent_activities (agent_name, action, entity_type, summary, details, status, created_at)
        VALUES (?, 'delegated', ?, ?, ?, 'completed', datetime('now'))
    """, ("orchestrator", "agent_task", f"Delegated to {to_agent}: {task[:100]}",
          f'{{"task_id": {task_id}, "to_agent": "{to_agent}"}}'))
    conn2.commit()
    conn2.close()
    
    return {
        "status": "delegated",
        "task_id": task_id,
        "to_agent": to_agent,
        "task": task[:200],
    }


def get_pending_agent_tasks(limit: int = 10) -> list:
    """Get pending agent tasks for execution."""
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_tasks WHERE status = 'pending' ORDER BY priority ASC, created_at ASC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def complete_agent_task(task_id: int, result: str):
    """Mark an agent task as completed."""
    with db_cursor() as conn:
        conn.execute("""
            UPDATE agent_tasks SET status = 'completed', result = ?, completed_at = datetime('now')
            WHERE id = ?
        """, (result, task_id))
