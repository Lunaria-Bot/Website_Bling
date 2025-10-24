import os
import asyncpg
import uuid
import aiohttp
from quart import Quart, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import check_password_hash

app = Quart(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
print("Webhook URL:", DISCORD_WEBHOOK_URL)

db_pool = None

@app.before_serving
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(
        dsn=os.getenv("DATABASE_URL"),
        ssl="require"
    )

@app.route("/")
async def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
async def login():
    if request.method == "POST":
        form = await request.form
        username = form["username"]
        password = form["password"]

        async with db_pool.acquire() as conn:
            admin = await conn.fetchrow(
                "SELECT id, username, password_hash, role FROM admins WHERE username=$1",
                username
            )

        if admin and check_password_hash(admin["password_hash"], password):
            session["user_id"] = admin["id"]
            session["username"] = admin["username"]
            session["role"] = admin["role"]
            flash("✅ Logged in successfully!")

            if admin["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            elif admin["role"] == "card_maker":
                return redirect(url_for("submit_card"))
            else:
                flash("❌ Unknown role")
        else:
            flash("❌ Invalid credentials")

    return await render_template("login.html")

@app.route("/cardmaker_login", methods=["GET", "POST"])
async def cardmaker_login():
    if request.method == "POST":
        form = await request.form
        username = form["username"]
        password = form["password"]

        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id, username, password_hash, role FROM admins WHERE username=$1",
                username
            )

        if user and user["role"] == "card_maker" and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("✅ Logged in as Card Maker")
            return redirect(url_for("submit_card"))
        else:
            flash("❌ Invalid credentials or role")

    return await render_template("cardmaker_login.html")

@app.route("/logout")
async def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("login"))

@app.route("/admin", methods=["GET", "POST"])
async def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":
        form = await request.form
        card_id = int(form["card_id"])
        action = form["action"]

        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE card_queue SET status=$1 WHERE id=$2",
                action, card_id
            )

        flash(f"✅ Card #{card_id} marked as {action}.")
        return redirect(url_for("admin_dashboard"))

    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM cards")
        base = await conn.fetchval("SELECT COUNT(*) FROM cards WHERE form='base'")
        awakened = await conn.fetchval("SELECT COUNT(*) FROM cards WHERE form='awakened'")
        event = await conn.fetchval("SELECT COUNT(*) FROM cards WHERE form='event'")
        recent = await conn.fetch("""
            SELECT id, character_name, form, image_url, series, created_at
            FROM cards ORDER BY created_at DESC LIMIT 5
        """)
        pending = await conn.fetch("""
            SELECT id, title, series, image_url, submitted_by, form_type, created_at
            FROM card_queue WHERE status = 'pending'
            ORDER BY created_at DESC LIMIT 5
        """)

    stats = {
        "total": total,
        "base": base,
        "awakened": awakened,
        "event": event,
        "recent": recent,
        "pending": pending
    }

    return await render_template("admin_dashboard.html", stats=stats)
@app.route("/history")
async def history():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    form_filter = request.args.get("form")
    search = request.args.get("search")

    async with db_pool.acquire() as conn:
        query = "SELECT id, character_name, form, image_url, series, created_at FROM cards"
        conditions = []
        params = []

        if form_filter and form_filter != "all":
            conditions.append(f"form = ${len(params)+1}")
            params.append(form_filter)

        if search:
            conditions.append(f"character_name ILIKE ${len(params)+1}")
            params.append(f"%{search}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT 50"
        cards = await conn.fetch(query, *params)

    return await render_template("history.html", cards=cards, form_filter=form_filter, search=search)

@app.route("/edit_card_list")
async def edit_card_list():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    async with db_pool.acquire() as conn:
        cards = await conn.fetch("""
            SELECT id, character_name, form, image_url, series, created_at
            FROM cards ORDER BY id DESC
        """)

    return await render_template("edit_card_list.html", cards=cards)

@app.route("/edit_card/<int:card_id>", methods=["GET", "POST"])
async def edit_card(card_id):
    async with db_pool.acquire() as conn:
        card = await conn.fetchrow("SELECT * FROM cards WHERE id = $1", card_id)
        if not card:
            abort(404)

        if request.method == "POST":
            form = await request.form
            name = form["character_name"]
            form_type = form["form"]
            image_url = form["image_url"]
            series = form["series"]

            await conn.execute("""
                UPDATE cards
                SET character_name = $1,
                    form = $2,
                    image_url = $3,
                    series = $4
                WHERE id = $5
            """, name, form_type, image_url, series, card_id)

            return redirect(url_for("edit_card_list"))

    return await render_template("edit_card_form.html", card=card)

@app.route("/add_card", methods=["GET", "POST"])
async def add_card():
    if request.method == "POST":
        form = await request.form
        name = form.get("base_name")
        form_type = form.get("form")
        image_url = form.get("image_url")
        series = form.get("series")

        if not name or not form_type or not image_url:
            await flash("❌ Missing required fields.")
            return redirect(url_for("add_card"))

        code = str(uuid.uuid4())

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO cards (code, character_name, form, image_url, series, created_at, approved)
                VALUES ($1, $2, $3, $4, $5, NOW(), TRUE)
            """, code, name, form_type, image_url, series)

        await flash(f"✅ Card '{name}' added successfully.")

        # 🔔 Webhook Discord
        if DISCORD_WEBHOOK_URL:
            embed = {
                "title": f"🆕 New Card Added: {name}",
                "description": f"**Form:** {form_type.capitalize()}\n**Series:** {series or '—'}",
                "color": 3447003,
                "image": {"url": image_url},
                "footer": {"text": f"Code: {code}"}
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}) as resp:
                    if resp.status != 204:
                        print(f"❌ Webhook failed: {resp.status}")

        return redirect(url_for("admin_dashboard"))

    return await render_template("add_card.html")

@app.route("/delete_card", methods=["POST"])
async def delete_card():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    form = await request.form
    try:
        card_id = int(form.get("card_id"))
    except (TypeError, ValueError):
        flash("❌ Invalid card ID.")
        return redirect(url_for("admin_dashboard"))

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM cards WHERE id=$1", card_id)

    flash("🗑️ Card deleted.")
    return redirect(url_for("edit_card_list"))

@app.route("/add_card_to_player", methods=["POST"])
async def add_card_to_player():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    form = await request.form
    player_id = int(form.get("player_id"))
    card_id = int(form.get("card_id"))
    discord_id = form.get("discord_id")

    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE cards SET owner_id=$1 WHERE id=$2", player_id, card_id)

    flash("✅ Card assigned to player!")
    return redirect(url_for("player_profile", discord_id=discord_id))

@app.route("/remove_card_from_player", methods=["POST"])
async def remove_card_from_player():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    form = await request.form
    card_id = int(form.get("card_id"))
    discord_id = form.get("discord_id")

    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE cards SET owner_id=NULL WHERE id=$1", card_id)

    flash("🗑️ Card removed from player.")
    return redirect(url_for("player_profile", discord_id=discord_id))

@app.route("/search_player", methods=["GET", "POST"])
async def search_player():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        form = await request.form
        discord_id = form.get("discord_id").strip()
        return redirect(url_for("player_profile", discord_id=discord_id))

    return await render_template("search_player.html")

@app.route("/profile/<discord_id>")
async def player_profile(discord_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    discord_id = str(discord_id).strip()

    async with db_pool.acquire() as conn:
        player = await conn.fetchrow("""
            SELECT id, discord_id, username, discord_tag, avatar_url, bloodcoins, noblecoins,
                   level, xp, achievements, created_at, updated_at, gate_keys
            FROM players
            WHERE discord_id = $1
        """, discord_id)

        if not player:
            return await render_template("player_not_found.html", discord_id=discord_id)

        cards = await conn.fetch("""
            SELECT id, character_name, image_url
            FROM cards
            WHERE owner_id = $1
            ORDER BY created_at DESC
        """, player["id"])

        all_cards = await conn.fetch("""
            SELECT id, character_name
            FROM cards
            WHERE owner_id IS NULL
            ORDER BY id DESC
        """)

    player = dict(player)
    player["xp_max"] = 172
    player["created_at"] = player["created_at"].strftime("%d %b %Y") if player["created_at"] else "Unknown"
    player["updated_at"] = player["updated_at"].strftime("%d %b %Y") if player["updated_at"] else "Unknown"

    return await render_template("profile.html", player=player, cards=cards, all_cards=all_cards)

@app.route("/manage")
async def manage():
    async with db_pool.acquire() as conn:
        admins = await conn.fetch("SELECT id, username, role FROM admins ORDER BY role DESC")

    return await render_template("manage.html", users=admins)

@app.route("/edit_user/<int:user_id>")
async def edit_user(user_id):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id, username, role FROM admins WHERE id = $1", user_id)

    if not user:
        flash("❌ User not found")
        return redirect(url_for("manage"))

    return await render_template("edit_user.html", user=user)

@app.route("/update_user", methods=["POST"])
async def update_user():
    form = await request.form
    user_id = int(form["user_id"])
    username = form["username"]
    role = form["role"]

    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE admins SET username=$1, role=$2 WHERE id=$3",
            username, role, user_id
        )

    flash("✅ User updated successfully")
    return redirect(url_for("manage"))

@app.route("/process_card", methods=["POST"])
async def process_card():
    form = await request.form
    card_id = form.get("card_id")
    action = form.get("action")

    if not card_id or not action:
        flash("❌ Missing card ID or action.")
        return redirect(url_for("admin_dashboard"))

    async with db_pool.acquire() as conn:
        try:
            card_id = int(card_id)
        except ValueError:
            flash("❌ Invalid card ID format.")
            return redirect(url_for("admin_dashboard"))

        if action == "approved":
            card = await conn.fetchrow("SELECT * FROM pending_cards WHERE id = $1", card_id)
            if not card:
                flash("❌ Card not found in pending submissions.")
                return redirect(url_for("admin_dashboard"))

            await conn.execute("""
                INSERT INTO cards (code, character_name, form, image_url, series, event_name, created_at, approved)
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), TRUE)
            """, card["id"], card["character_name"], card["form"], card["image_url"], card["series"], card["event_name"])

            await conn.execute("DELETE FROM pending_cards WHERE id = $1", card_id)
            await conn.execute("INSERT INTO card_queue (card_id, action) VALUES ($1, 'add')", card["id"])
            flash(f"✅ Card '{card['character_name']}' approved.")

            # 🔔 Webhook Discord
            if DISCORD_WEBHOOK_URL:
                embed = {
                    "title": f"✅ New Card Approved: {card['character_name']}",
                    "description": f"**Form:** {card['form'].capitalize()}\n**Series:** {card['series'] or '—'}\n**Event:** {card['event_name'] or '—'}",
                    "color": 3066993,
                    "image": {"url": card["image_url"]},
                    "footer": {"text": f"Card ID: {card['id']}"}
                }
                async with aiohttp.ClientSession() as session:
                    await session.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})

        elif action == "rejected":
            await conn.execute("DELETE FROM pending_cards WHERE id = $1", card_id)
            flash("🗑️ Card rejected and removed.")

        else:
            flash("❌ Unknown action.")
            return redirect(url_for("admin_dashboard"))

    return redirect(url_for("admin_dashboard"))
