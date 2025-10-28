import asyncpg
from datetime import datetime

async def dashboard_data(pool):
    async with pool.acquire() as conn:
        # Count by form
        form_counts = await conn.fetch("""
            SELECT form, COUNT(*) AS count
            FROM cards
            GROUP BY form
        """)

        # Recent cards (last 5)
        recent = await conn.fetch("""
            SELECT id, character_name, form, created_at, series
            FROM cards
            ORDER BY created_at DESC
            LIMIT 5
        """)

        # Pending submissions
        pending = await conn.fetch("""
            SELECT id, title, form_type, series, image_url, submitted_by
            FROM submissions
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT 5
        """)

    # Fallbacks
    form_map = {"base": 0, "awakened": 0, "event": 0}
    for row in form_counts:
        form_map[row["form"]] = row["count"]

    recent_cards = [
        {
            "id": r["id"],
            "character_name": r["character_name"],
            "form": r["form"],
            "created_at": r["created_at"].strftime("%Y-%m-%d"),
            "series": r["series"]
        }
        for r in recent
    ]

    pending_cards = [
        {
            "id": p["id"],
            "title": p["title"],
            "form_type": p["form_type"],
            "series": p["series"],
            "image_url": p["image_url"],
            "submitted_by": p["submitted_by"]
        }
        for p in pending
    ]

    return {
        "base": form_map["base"],
        "awakened": form_map["awakened"],
        "event": form_map["event"],
        "recent": recent_cards,
        "pending": pending_cards
    }
