"""
CreatorForge OS — Seed Data
Creates demo creator "Layla Makes" with products, deals, content, and historical patterns.
"""
from models import db_cursor, init_db


def seed():
    init_db()
    with db_cursor() as conn:
        # Check if already seeded
        count = conn.execute("SELECT COUNT(*) FROM creators").fetchone()[0]
        if count > 0:
            print("Already seeded, skipping.")
            return

        # Creator
        conn.execute("""
            INSERT INTO creators (name, handle, bio, niche, followers, monthly_revenue, cleared_revenue, avatar)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Layla Makes", "layla.makes",
            "Songwriter & producer. Sample packs, courses & 1:1 sessions.",
            "music", 184000, 12400, 9200, "🎵"
        ))
        creator_id = conn.execute("SELECT id FROM creators WHERE handle = 'layla.makes'").fetchone()[0]

        # Products
        products = [
            ("Lo-fi Sample Pack Vol.3", "120 royalty-free lo-fi samples, loops, and MIDI kits.", 48, 1204, "sample-pack", "🎧"),
            ("Songwriting Course", "8-module course: from hook to finished song.", 89, 860, "course", "🎓"),
            ("1:1 Studio Session", "60-minute private production session via Zoom.", 120, 12, "service", "🎙️"),
            ("Beat Maker's Toolkit", "50 production templates for Ableton & FL Studio.", 35, 643, "template", "🎛️"),
        ]
        for p in products:
            conn.execute("""
                INSERT INTO products (creator_id, title, description, price, sales_count, category, image_emoji)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (creator_id, p[0], p[1], p[2], p[3], p[4], p[5]))

        # Historical deals (some accepted, some declined — for memory patterns)
        historical_deals = [
            ("Aura Audio", "audio hardware", "sponsorship", 2800, "approved", 0.85,
             "Headphone brand sponsoring your production content.", 3200),
            ("Nimbus Strings", "music software", "collab", 1500, "approved", 0.78,
             "String library collaboration for sample pack.", 1800),
            ("Verve Studio", "audio hardware", "sponsorship", 3500, "approved", 0.82,
             "Studio monitor brand deal with content deliverables.", 4000),
            ("FitFuel Co", "fitness nutrition", "sponsorship", 2000, "declined", 0.25,
             "Protein powder brand — off-brand for music niche.", 2000),
            ("BeatCraft", "music software", "sponsorship", 2200, "approved", 0.88,
             "Beat-making software sponsorship — perfect niche fit.", 2500),
            ("GlowUp Cosmetics", "beauty", "sponsorship", 3000, "declined", 0.20,
             "Cosmetics brand — not aligned with music audience.", 3000),
            ("MidiMatters", "music hardware", "collab", 1800, "approved", 0.80,
             "MIDI controller collaboration with tutorial content.", 2100),
        ]
        for d in historical_deals:
            conn.execute("""
                INSERT INTO deals (creator_id, brand_name, brand_type, deal_type, offer_amount,
                status, fit_score, description, negotiated_amount, agent_analysis, needs_approval)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (creator_id, d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7],
                  f"Historical deal — analyzed and {d[4]}.", 0))

        # New inbound deals (pending analysis — for agent demo)
        new_deals = [
            ("SonarTech", "audio hardware", "sponsorship", 3500,
             "Wireless studio earbuds brand wants a dedicated review + story set."),
            ("RhythmBox", "music software", "collab", 1200,
             "Beat-making app wants a collab tutorial with their app."),
            ("GreenLeaf Tea", "lifestyle food", "sponsorship", 4000,
             "Tea brand targeting creators — wants lifestyle integration content."),
            ("SynthWave Pro", "music software", "sponsorship", 5000,
             "Professional synth plugin wants 3-part tutorial series."),
        ]
        for d in new_deals:
            conn.execute("""
                INSERT INTO deals (creator_id, brand_name, brand_type, deal_type, offer_amount,
                description, status, needs_approval)
                VALUES (?, ?, ?, ?, ?, ?, 'pending_analysis', 0)
            """, (creator_id, d[0], d[1], d[2], d[3], d[4]))

        # Content items
        content_items = [
            ("Behind the Beat: Lo-fi Sample Pack Vol.3", "post",
             "Show the process of creating the sample pack — DAW screenshots, sound design walkthrough.",
             "published", "instagram"),
            ("5 Songwriting Techniques That Changed My Process", "video",
             "Tutorial-style long-form content about songwriting methods.",
             "published", "youtube"),
            ("Studio Session Highlights", "reel",
             "Short clips from 1:1 sessions showing student progress.",
             "published", "instagram"),
            ("New Beat Making Tutorial with SynthWave Pro", "video",
             "Sponsored tutorial using SynthWave Pro plugin — 3 part series.",
             "brief", "youtube"),
            ("Productivity Hacks for Music Producers", "post",
             "Tips on workflow, session organization, and creative routines.",
             "draft", "instagram"),
        ]
        for c in content_items:
            conn.execute("""
                INSERT INTO content_items (creator_id, title, content_type, brief, status, platform)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (creator_id, c[0], c[1], c[2], c[3], c[4]))

        # Invoices
        invoices = [
            ("Aura Audio", 3200, "paid", 1),
            ("Nimbus Strings", 1800, "paid", 1),
            ("Verve Studio", 4000, "paid", 1),
            ("BeatCraft", 2500, "paid", 1),
            ("MidiMatters", 2100, "paid", 1),
        ]
        for inv in invoices:
            conn.execute("""
                INSERT INTO invoices (creator_id, client_name, amount, status, deal_id)
                VALUES (?, ?, ?, ?, ?)
            """, (creator_id, inv[0], inv[1], inv[2], inv[3]))

        # Memory patterns (pre-seeded for demo, will be updated by memory agent)
        patterns = [
            ("deal_acceptance", "overall_rate", "71%", 0.78, 7,
             "You accept 71% of inbound deals. Audio/music brands have near-perfect acceptance. Fitness/beauty are auto-declined."),
            ("brand_fit", "music_brands", "5 deals, avg $2,520", 0.85, 5,
             "Music industry brands are your strongest fit — 5 deals averaging $2,520. Audio hardware and software brands convert highest."),
            ("brand_fit", "off_brand_decline", "2 deals declined", 0.90, 2,
             "Fitness (FitFuel) and beauty (GlowUp) brands were declined — low audience overlap with music niche."),
            ("content_performance", "top_platform", "Instagram", 0.75, 3,
             "Instagram is your most active platform. Reels perform best for music production content."),
            ("deal_revenue", "avg_deal_value", "$2,520", 0.80, 5,
             "Average accepted deal value is $2,520. Deals above $2,000 with music brands have 100% acceptance rate."),
        ]
        for p in patterns:
            conn.execute("""
                INSERT INTO memory_patterns (creator_id, pattern_type, pattern_key, pattern_value,
                confidence, sample_count, insight)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (creator_id, p[0], p[1], p[2], p[3], p[4], p[5]))

        # Initial agent activities
        activities = [
            ("deal_agent", "system_init", "Deal Agent initialized — monitoring inbound brand deals.", "completed"),
            ("content_agent", "system_init", "Content Agent initialized — ready to draft content from briefs.", "completed"),
            ("finance_agent", "system_init", "Finance Agent initialized — tracking invoices and payments.", "completed"),
            ("memory_agent", "system_init", "Memory Agent initialized — 5 patterns loaded from 7 historical deals.", "completed"),
            ("deal_agent", "new_deals_detected", "4 new inbound deals detected — pending analysis. Ready to process.", "completed"),
        ]
        for a in activities:
            conn.execute("""
                INSERT INTO agent_activities (agent_name, action, summary, status)
                VALUES (?, ?, ?, ?)
            """, (a[0], a[1], a[2], a[3]))

    print("✅ Seed data loaded: Layla Makes (@layla.makes)")
    print(f"   Creator: 184K followers, $12.4K monthly revenue")
    print(f"   Products: 4, Historical deals: 7, New deals: 4 (pending)")
    print(f"   Content: 5 items, Invoices: 5 (paid)")
    print(f"   Memory: 5 patterns pre-loaded")
    print(f"   Agents: 4 initialized and ready")


if __name__ == "__main__":
    seed()
