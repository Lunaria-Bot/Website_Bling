from quart import Blueprint, render_template, session, redirect, url_for
import asyncpg

player_bp = Blueprint("player", __name__)

# Replace with your actual DB pool
db_pool: asyncpg.pool.Pool = None

def require_login():
    if not session.get("discord_id"):
        return redirect(url_for("authy.login"))

@player_bp.route("/profile")
async def profile():
    if not session.get("discord_id"):
        return redirect(url_for("authy.login"))

    discord_id = str(session["discord_id"])
    async with db_pool.acquire() as conn:
        player = await conn.fetchrow("SELECT * FROM players WHERE discord_id = $1", discord_id)
        if not player:
            return await render_template("player/profile.html", error="No profile found.")

    return await render_template("player/profile.html", player=player)

@player_bp.route("/inventory")
async def inventory():
    if not session.get("discord_id"):
        return redirect(url_for("authy.login"))

    discord_id = str(session["discord_id"])
    async with db_pool.acquire() as conn:
        user_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
        cards = await conn.fetch("""
            SELECT c.character_name, c.form, c.series, c.image_url,
                   uc.quantity, uc.xp, uc.health, uc.attack, uc.speed
            FROM user_cards uc
            JOIN cards c ON c.id = uc.card_id
            WHERE uc.user_id = $1
            ORDER BY c.character_name
        """, user_id)

    return await render_template("player/inventory.html", cards=cards)

@player_bp.route("/team")
async def team():
    if not session.get("discord_id"):
        return redirect(url_for("authy.login"))

    discord_id = str(session["discord_id"])
    async with db_pool.acquire() as conn:
        user_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
        team = await conn.fetch("""
            SELECT pt.slot, pt.is_captain,
                   c.character_name, c.form, c.series, c.image_url,
                   uc.xp, uc.health, uc.attack, uc.speed
            FROM player_team pt
            JOIN user_cards uc ON uc.card_id = pt.card_id AND uc.user_id = pt.user_id
            JOIN cards c ON c.id = pt.card_id
            WHERE pt.user_id = $1
            ORDER BY pt.slot
        """, user_id)

    return await render_template("player/team.html", team=team)
