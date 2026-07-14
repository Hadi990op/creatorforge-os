"""
CreatorForge OS — LLM Abstraction Layer
=======================================
Backward-compatible interface that delegates to the multi-provider
llm_engine. Rule-based fallbacks remain as last resort.

Provider chain (automatic failover):
  1. User-configured providers (Groq, Gemini, OpenRouter, Cerebras, Mistral)
  2. LLM7.io free tier (no key needed — gemma3:27b, codestral-latest)
  3. Rule-based fallback (always works)
"""
import os
import json
import random
from typing import Optional

# Re-export from the new engine for backward compatibility
from llm_engine import (
    has_any_llm as _has_any,
    llm_chat,
    llm_chat_json,
    llm_chat_json_list,
    get_active_provider,
    get_provider_status,
    reload_providers,
    add_provider_key,
    remove_provider_key,
)

HAS_LLM = True  # always true — at minimum LLM7.io free tier works


async def llm_analyze(prompt: str, system: str = "", max_tokens: int = 800) -> str:
    """Backward-compatible wrapper. Returns text or empty string."""
    text, provider = await llm_chat(prompt, system=system, max_tokens=max_tokens)
    return text


# ── Rule-based fallbacks for each agent ──
# (These remain as the final fallback when all LLM providers fail)

def deal_agent_fallback(brand_name: str, brand_type: str, offer_amount: float,
                        deal_type: str, creator_niche: str, creator_followers: int,
                        description: str) -> dict:
    """Sophisticated rule-based deal analysis."""
    niche_lower = creator_niche.lower() if creator_niche else ""
    brand_lower = (brand_name + " " + brand_type + " " + description).lower()

    niche_keywords = {
        "music": [
            ("audio", 1.0), ("music", 1.0), ("sound", 0.8), ("studio", 0.9),
            ("beat", 0.8), ("sample", 0.9), ("instrument", 0.8), ("headphone", 0.7),
            ("speaker", 0.7), ("synth", 0.9), ("synthwave", 1.0), ("plugin", 0.9),
            ("daw", 0.9), ("midi", 0.9), ("production", 0.8), ("loop", 0.7),
            ("vocal", 0.7), ("recording", 0.8), ("mixer", 0.8), ("producer", 0.9),
            ("songwriter", 0.9), ("songwriting", 0.9), ("composer", 0.8),
            ("earbud", 0.6), ("wireless", 0.3),
        ],
        "tech": [
            ("tech", 1.0), ("software", 0.9), ("app", 0.7), ("gadget", 0.8),
            ("device", 0.7), ("saas", 0.9), ("platform", 0.7), ("ai", 0.6),
        ],
        "fitness": [
            ("fitness", 1.0), ("gym", 0.9), ("health", 0.8), ("workout", 0.9),
            ("nutrition", 0.8), ("protein", 0.9), ("wellness", 0.7),
        ],
        "beauty": [
            ("beauty", 1.0), ("cosmetic", 1.0), ("skincare", 1.0), ("makeup", 1.0),
            ("fashion", 0.8), ("glow", 0.7),
        ],
        "gaming": [
            ("game", 1.0), ("gaming", 1.0), ("esports", 1.0), ("stream", 0.8),
            ("twitch", 0.9), ("console", 0.8), ("controller", 0.8),
        ],
        "food": [
            ("food", 1.0), ("restaurant", 0.9), ("recipe", 1.0), ("cook", 0.8),
            ("kitchen", 0.8), ("snack", 0.9), ("tea", 0.7), ("coffee", 0.8),
        ],
        "lifestyle": [
            ("lifestyle", 1.0), ("travel", 0.9), ("home", 0.7), ("decor", 0.9),
            ("wellness", 0.8), ("tea", 0.6), ("coffee", 0.6),
        ],
    }

    keywords = niche_keywords.get(niche_lower, [])
    if not keywords:
        all_kw = set()
        for kw_list in niche_keywords.values():
            for kw, _ in kw_list:
                all_kw.add(kw)
        match_count = sum(1 for kw in all_kw if kw in brand_lower)
        base_fit = 0.3 + (match_count / max(len(all_kw), 1)) * 0.4
    else:
        total_weight = 0
        matched_weight = 0
        for kw, weight in keywords:
            total_weight += weight
            if kw in brand_lower:
                matched_weight += weight
        match_ratio = matched_weight / max(total_weight, 1)
        has_strong_match = any(w >= 0.8 and kw in brand_lower for kw, w in keywords)
        if has_strong_match and match_ratio >= 0.04:
            base_fit = 0.42 + match_ratio * 0.55
        else:
            base_fit = 0.28 + match_ratio * 0.40

    if creator_followers > 500000:
        benchmark = 5000 + creator_followers * 0.01
    elif creator_followers > 100000:
        benchmark = 2000 + creator_followers * 0.02
    elif creator_followers > 10000:
        benchmark = 500 + creator_followers * 0.05
    else:
        benchmark = 100 + creator_followers * 0.1

    offer = offer_amount or 0
    price_ratio = offer / benchmark if benchmark > 0 else 0

    if price_ratio > 1.2:
        price_assessment = "above market"
        negotiation_target = offer
    elif price_ratio > 0.8:
        price_assessment = "fair market value"
        negotiation_target = offer * 1.15
    else:
        price_assessment = "below market"
        negotiation_target = max(benchmark * 0.9, offer * 1.3)

    fit_score = min(0.98, base_fit + (0.05 if price_ratio > 0.8 else 0))
    fit_score = max(0.15, fit_score)

    if fit_score > 0.70:
        recommendation = "strong_fit"
        reasoning = f"Strong brand-creator alignment. {brand_name} operates in {brand_type or 'a space'} that closely matches your {creator_niche or 'creative'} niche. Audience overlap is high, making this a natural partnership."
    elif fit_score >= 0.45:
        recommendation = "moderate_fit"
        reasoning = f"Reasonable fit. {brand_name} has some audience overlap with your {creator_niche or 'content'} niche. The deal is viable but may require creative alignment on deliverables."
    else:
        recommendation = "off_brand"
        reasoning = f"Low brand-creator fit. {brand_name} doesn't align strongly with your {creator_niche or 'creative'} niche. Your audience may not engage authentically with this brand."

    negotiation_terms = f"Counter at ${negotiation_target:,.0f} with 2 deliverables (1 dedicated post + 1 story set), 30-day usage rights, performance bonus if >5% engagement."

    return {
        "fit_score": round(fit_score, 2),
        "fit_reasoning": reasoning,
        "recommendation": recommendation,
        "price_assessment": price_assessment,
        "benchmark_price": round(benchmark, 2),
        "negotiated_amount": round(negotiation_target, 2),
        "negotiated_terms": negotiation_terms,
        "agent_analysis": f"Analyzed {brand_name} against creator profile ({creator_followers:,} followers, {creator_niche} niche). Fit score: {fit_score:.0%}. Price assessment: {price_assessment}. Market benchmark: ${benchmark:,.0f}. Recommendation: {recommendation}.",
    }


def content_agent_fallback(title: str, brief: str, content_type: str,
                           platform: str, creator_niche: str) -> dict:
    """Rule-based content draft generation."""
    niche = creator_niche or "creative"

    hooks = {
        "music": f"Ever wondered what goes into making {title.lower()}? Here's the behind-the-scenes most people never see.",
        "tech": f"I've been testing {title} for weeks. Here's what nobody is telling you.",
        "fitness": f"The truth about {title.lower()} — it's not what you think. Here's what actually works.",
        "beauty": f"Everyone asks me about {title.lower()}. Today I'm showing you exactly how I do it.",
        "gaming": f"This {title} changes everything. Here's why you need to see this.",
        "food": f"The simplest way to make {title.lower()} — and it tastes incredible.",
        "lifestyle": f"Let's talk about {title.lower()}. It changed how I approach my work.",
    }

    hook = hooks.get(niche, f"Here's something about {title.lower()} that took me years to figure out.")

    body = f"{hook}\n\n"
    if brief:
        body += f"{brief}\n\n"
    body += f"This is what I love about being a {niche} creator — the ability to share process, not just product.\n\n"
    body += f"Swipe to see the full breakdown. Save this for later — you'll need it.\n\n"
    body += f"What would you add? Drop a comment below. 👇"

    hashtags_map = {
        "music": "#producerlife #studiotime #musicproduction #beatmaker #newsound",
        "tech": "#techtok #techtips #innovation #digitaltools #creators",
        "fitness": "#fitness #workout #fitnesstips #healthylifestyle #gymmotivation",
        "beauty": "#beauty #skincareroutine #makeuptutorial #beautytips #glowup",
        "gaming": "#gaming #gameplay #gamer #streaming #esports",
        "food": "#foodie #recipe #homecooking #easyrecipe #foodlover",
        "lifestyle": "#lifestyle #creatorlife #productivity #mindset #dailyhabits",
    }

    hashtags = hashtags_map.get(niche, "#creator #content #passion #craft #community")

    platform_notes = {
        "instagram": "Reel format: 15-30s, hook in first 2 seconds, trending audio recommended",
        "youtube": "Long-form: 8-12 min, strong thumbnail needed, chapters for retention",
        "tiktok": "Short form: 15-60s, raw aesthetic, trending sound, strong CTA",
        "twitter": "Thread format: 5-8 tweets, hook tweet + breakdown + CTA",
    }

    return {
        "draft": body,
        "hashtags": hashtags,
        "platform_notes": platform_notes.get(platform, "Optimize for engagement in first 3 seconds"),
        "agent_reasoning": f"Drafted {content_type} for {platform} based on brief: '{brief[:80]}...' Tailored hook for {niche} niche audience. Added platform-specific optimization notes.",
    }


def finance_agent_fallback(client_name: str, amount: float, deal_type: str,
                           creator_name: str) -> dict:
    """Rule-based invoice generation."""
    from datetime import datetime, timedelta
    due = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    items = json.dumps([
        {"description": f"{deal_type or 'Sponsored content'} — {client_name}", "amount": amount},
        {"description": "Platform fee waiver (creator-direct)", "amount": 0},
    ])

    notes = f"Invoice generated for {client_name}. Net-30 terms. Payment via direct transfer or Stripe. Late fee: 1.5% per month after due date."

    return {
        "items": items,
        "due_date": due,
        "agent_notes": notes,
    }


def memory_agent_fallback(deals: list, content_items: list, creator_niche: str) -> list:
    """Rule-based pattern extraction from historical data."""
    patterns = []

    if not deals:
        return patterns

    accepted = [d for d in deals if d.get("status") in ("approved", "closed")]
    declined = [d for d in deals if d.get("status") == "declined"]
    all_deals = accepted + declined

    if len(all_deals) >= 2:
        avg_accepted = sum(d["offer_amount"] or 0 for d in accepted) / max(len(accepted), 1)
        avg_declined = sum(d["offer_amount"] or 0 for d in declined) / max(len(declined), 1) if declined else 0

        acceptance_rate = len(accepted) / len(all_deals) * 100
        patterns.append({
            "pattern_type": "deal_acceptance",
            "pattern_key": "overall_acceptance_rate",
            "pattern_value": f"{acceptance_rate:.0f}%",
            "confidence": min(0.95, 0.4 + len(all_deals) * 0.1),
            "sample_count": len(all_deals),
            "insight": f"You accept {acceptance_rate:.0f}% of inbound deals. Accepted deals average ${avg_accepted:,.0f}. " +
                       (f"Declined deals averaged ${avg_declined:,.0f} — typically off-brand or below market." if declined else ""),
        })

    brand_types = {}
    for d in accepted:
        bt = d.get("brand_type") or "unknown"
        if bt not in brand_types:
            brand_types[bt] = {"count": 0, "total": 0}
        brand_types[bt]["count"] += 1
        brand_types[bt]["total"] += d.get("offer_amount") or 0

    for bt, data in brand_types.items():
        if data["count"] >= 1:
            avg = data["total"] / data["count"]
            patterns.append({
                "pattern_type": "brand_fit",
                "pattern_key": f"brand_type_{bt}",
                "pattern_value": f"{data['count']} deals, avg ${avg:,.0f}",
                "confidence": min(0.9, 0.3 + data["count"] * 0.15),
                "sample_count": data["count"],
                "insight": f"{bt} brands have a {data['count']}-deal history with you, averaging ${avg:,.0f} per deal.",
            })

    published = [c for c in content_items if c.get("status") == "published"]
    if len(published) >= 2:
        platforms = {}
        for c in published:
            p = c.get("platform", "unknown")
            platforms[p] = platforms.get(p, 0) + 1
        top_platform = max(platforms, key=platforms.get)
        patterns.append({
            "pattern_type": "content_performance",
            "pattern_key": "top_platform",
            "pattern_value": top_platform,
            "confidence": min(0.85, 0.3 + len(published) * 0.1),
            "sample_count": len(published),
            "insight": f"{top_platform.capitalize()} is your most published platform with {platforms[top_platform]} posts. Consistent publishing here builds audience expectation.",
        })

    return patterns
