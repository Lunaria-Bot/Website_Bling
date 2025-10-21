import os
import asyncio
import asyncpg
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

loop = asyncio.get_event_loop()
db_pool = loop.run_until_complete(asyncpg.create_pool(
    dsn=os.getenv("DATABASE_URL"),
    ssl="require"
))

# --- Authentication ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        async def fetch_admin():
            async with db_pool.acquire() as conn:
                return await conn.fetchrow(
                    "SELECT id, username, password_hash, role FROM admins WHERE username=$1",
                    username
                )

        admin = loop.run_until_complete(fetch_admin())
        if admin and check_password_hash(admin["password_hash"], password):
            session["user_id"] = admin["id"]
            session["username"] = admin["username"]
            session["role"] = admin["role"]
            flash("✅ Logged in successfully!")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("❌ Invalid credentials")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("login"))

# --- Admin Dashboard ---
@app.route("/admin")
def admin_dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    async def fetch_stats_and_recent():
        async with db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM cards")
            base = await conn.fetchval("SELECT COUNT(*) FROM cards WHERE form='base'")
            awakened = await conn.fetchval("SELECT COUNT(*) FROM cards WHERE form='awakened'")
            event = await conn.fetchval("SELECT COUNT(*) FROM cards WHERE form='event'")
            recent = await conn.fetch("""
                SELECT id, character_name, form, image_url, description, created_at
                FROM cards ORDER BY created_at DESC LIMIT 5
            """)
            return {
                "total": total,
                "base": base,
                "awakened": awakened,
                "event": event,
                "recent": recent
            }

    stats = loop.run_until_complete(fetch_stats_and_recent())
    return render_template("admin_dashboard.html", user=session.get("username"), stats=stats)

# --- Add Card ---
@app.route("/", methods=["GET", "POST"])
def add_card():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        base_name = request.form["base_name"]
        description = request.form["description"]
        forms = ["base", "awakened", "event"]

        async def insert_cards():
            async with db_pool.acquire() as conn:
                for form in forms:
                    character_name = f"{base_name} ({form.capitalize()})"
                    image_url = request.form[f"image_{form}"]
                    await conn.execute("""
                        INSERT INTO cards (character_name, form, image_url, description)
                        VALUES ($1, $2, $3, $4)
                    """, character_name, form, image_url, description)

        loop.run_until_complete(insert_cards())
        flash("✅ All forms added successfully!")
        return redirect(url_for("add_card"))

    return render_template("add_card.html")

# --- History ---
@app.route("/history")
def history():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    form_filter = request.args.get("form")
    search = request.args.get("search")

    async def fetch_cards():
        async with db_pool.acquire() as conn:
            query = "SELECT id, character_name, form, image_url, description, created_at FROM cards"
            conditions = []
            params = []
            if form_filter and form_filter != "all":
                conditions.append("form = $%d" % (len(params)+1))
                params.append(form_filter)
            if search:
                conditions.append("character_name ILIKE $%d" % (len(params)+1))
                params.append(f"%{search}%")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC LIMIT 50"
            return await conn.fetch(query, *params)

    cards = loop.run_until_complete(fetch_cards())
    return render_template("history.html", cards=cards, form_filter=form_filter, search=search)

# --- Edit Card List ---
@app.route("/edit_card")
def edit_card_list():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    async def fetch_all_cards():
        async with db_pool.acquire() as conn:
            return await conn.fetch("SELECT id, character_name, form, image_url, description, created_at FROM cards ORDER BY id DESC")

    cards = loop.run_until_complete(fetch_all_cards())
    return render_template("edit_card_list.html", cards=cards)

# --- Edit Specific Card ---
@app.route("/edit/<int:card_id>", methods=["GET", "POST"])
def edit_card(card_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    async def fetch_card():
        async with db_pool.acquire() as conn:
            return await conn.fetchrow("SELECT id, character_name, form, image_url, description FROM cards WHERE id=$1", card_id)

    card = loop.run_until_complete(fetch_card())
    if not card:
        flash(f"❌ Card with ID {card_id} not found")
        return redirect(url_for("edit_card_list"))

    if request.method == "POST":
        character_name = request.form["character_name"]
        form = request.form["form"]
        image_url = request.form["image_url"]
        description = request.form["description"]

        async def update_card():
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE cards SET character_name=$1, form=$2, image_url=$3, description=$4 WHERE id=$5
                """, character_name, form, image_url, description, card_id)

        loop.run_until_complete(update_card())
        flash(f"✅ Card #{card_id} updated successfully!")
        return redirect(url_for("edit_card_list"))

    return render_template("edit_card.html", card=card)

# --- Delete Card ---
@app.route("/delete_card", methods=["POST"])
def delete_card():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    card_id = request.form.get("card_id")

    async def delete():
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM cards WHERE id=$1", int(card_id))

    loop.run_until_complete(delete())
    flash("🗑️ Card deleted.")
    return redirect(url_for("edit_card_list"))

# --- Player Profile ---
@app.route("/player/<discord_id>")
def player_profile(discord_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    async def fetch_player_and_cards():
        async with db_pool.acquire() as conn:
            player = await conn.fetchrow("SELECT id, discord_id, name, bloodcoins FROM players WHERE discord_id=$1", discord_id)
            if not player:
                return None, [], []
            cards = await conn.fetch("SELECT * FROM cards WHERE owner_id=$1 ORDER BY created_at DESC", player["id"])
            all_cards = await conn.fetch("SELECT id, character_name FROM cards WHERE owner_id IS NULL ORDER BY id DESC")
            return player, cards, all_cards

    player, cards, all_cards = loop.run_until_complete(fetch_player_and_cards())
    if not player:
        flash(f"❌ No player found with Discord ID {discord_id}")
        return redirect(url_for("admin_dashboard"))

    return render_template("player_profile.html", player=player, cards=cards, all_cards=all_cards)

@app.route("/add_card_to_player", methods=["POST"])
def add_card_to_player():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    player_id = request.form.get("player_id")
    card_id = request.form.get("card_id")
    discord_id = request.form.get("discord_id")

    async def assign_card():
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE cards SET owner_id=$1 WHERE id=$2", int(player_id), int(card_id))

    loop.run_until_complete(assign_card())
    flash("✅ Card assigned to player!")
    return redirect(url_for("player_profile", discord_id=discord_id))

@app.route("/remove_card_from_player", methods=["POST"])
def remove_card_from_player():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    card_id = request.form.get("card_id")
    discord_id = request.form.get("discord_id")

    async def unassign_card():
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE cards SET owner_id=NULL WHERE id=$1", int(card_id))

    loop.run_until_complete(unassign_card())
    flash("🗑️ Card removed from player.")
    return redirect(url_for("player_profile", discord_id=discord_id))

# --- Search Player ---
@app.route("/search_player", methods=["GET", "POST"])
def search_player():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        discord_id = request.form.get("discord_id")
        return redirect(url_for("player_profile", discord_id=discord_id))

    return render_template("search_player.html")

# --- Run Server ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

