import os
import asyncio
import asyncpg
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.config["DEBUG"] = True
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

loop = asyncio.get_event_loop()
db_pool = loop.run_until_complete(asyncpg.create_pool(
    dsn=os.getenv("DATABASE_URL"),
    ssl="require"
))

# --- Login ---
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
            if admin["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            elif admin["role"] == "card_maker":
                return redirect(url_for("submit_card"))
            else:
                flash("❌ Unknown role")
        else:
            flash("❌ Invalid credentials")

    return render_template("login.html")

@app.route("/cardmaker_login", methods=["GET", "POST"])
def cardmaker_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        async def fetch_user():
            async with db_pool.acquire() as conn:
                return await conn.fetchrow(
                    "SELECT id, username, password_hash, role FROM admins WHERE username=$1",
                    username
                )

        user = loop.run_until_complete(fetch_user())
        if user and user["role"] == "card_maker" and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("✅ Logged in as Card Maker")
            return redirect(url_for("submit_card"))
        else:
            flash("❌ Invalid credentials or role")

    return render_template("cardmaker_login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("login"))
# --- Edit Card List ---
@app.route("/edit_card_list")
async def edit_card_list():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    async with db_pool.acquire() as conn:
        cards = await conn.fetch("""
            SELECT id, character_name, form, image_url, description, created_at
            FROM cards ORDER BY id DESC
        """)

    return await render_template("edit_card_list.html", cards=cards)

# --- Edit Specific Card ---
@app.route("/edit_card/<int:card_id>", methods=["GET", "POST"])
async def edit_card(card_id):
    async with db_pool.acquire() as conn:
        card = await conn.fetchrow("SELECT * FROM cards WHERE id = $1", card_id)
        if not card:
            abort(404)

        if request.method == "POST":
            name = request.form["character_name"]
            form = request.form["form"]
            image_url = request.form["image_url"]
            description = request.form["description"]

            await conn.execute("""
                UPDATE cards
                SET character_name = $1,
                    form = $2,
                    image_url = $3,
                    description = $4
                WHERE id = $5
            """, name, form, image_url, description, card_id)

            return redirect(url_for("edit_card_list"))

    return await render_template("edit_card_form.html", card=card)

# --- Delete Card ---
@app.route("/delete_card", methods=["POST"])
async def delete_card():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    card_id = int(request.form.get("card_id"))
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM cards WHERE id=$1", card_id)

    flash("🗑️ Card deleted.")
    return redirect(url_for("edit_card_list"))

# --- Player Profile ---
@app.route("/player/<discord_id>")
async def player_profile(discord_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    discord_id = str(discord_id).strip()

    async with db_pool.acquire() as conn:
        player = await conn.fetchrow("SELECT * FROM players WHERE discord_id=$1", discord_id)
        if not player:
            return await render_template("player_not_found.html", discord_id=discord_id)

        cards = await conn.fetch("SELECT * FROM cards WHERE owner_id=$1 ORDER BY created_at DESC", player["id"])
        all_cards = await conn.fetch("SELECT id, character_name FROM cards WHERE owner_id IS NULL ORDER BY id DESC")

    player = dict(player)
    player["xp_max"] = 172
    player["created_at"] = player["created_at"].strftime("%d %b %Y") if player["created_at"] else "Unknown"
    player["updated_at"] = player["updated_at"].strftime("%d %b %Y") if player["updated_at"] else "Unknown"

    return await render_template("player_profile.html", player=player, cards=cards, all_cards=all_cards)

# --- Assign Card to Player ---
@app.route("/add_card_to_player", methods=["POST"])
async def add_card_to_player():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    player_id = int(request.form.get("player_id"))
    card_id = int(request.form.get("card_id"))
    discord_id = request.form.get("discord_id")

    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE cards SET owner_id=$1 WHERE id=$2", player_id, card_id)

    flash("✅ Card assigned to player!")
    return redirect(url_for("player_profile", discord_id=discord_id))

# --- Remove Card from Player ---
@app.route("/remove_card_from_player", methods=["POST"])
async def remove_card_from_player():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    card_id = int(request.form.get("card_id"))
    discord_id = request.form.get("discord_id")

    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE cards SET owner_id=NULL WHERE id=$1", card_id)

    flash("🗑️ Card removed from player.")
    return redirect(url_for("player_profile", discord_id=discord_id))

# --- Search Player ---
@app.route("/search_player", methods=["GET", "POST"])
async def search_player():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        discord_id = request.form.get("discord_id").strip()
        return redirect(url_for("player_profile", discord_id=discord_id))

    return await render_template("search_player.html")

# --- Manager ---
@app.route("/manage")
async def manage():
    async with db_pool.acquire() as conn:
        admins = await conn.fetch("SELECT id, username, role FROM admins ORDER BY role DESC")

    return await render_template("manage.html", users=admins)

# --- Edit User ---
@app.route("/edit_user/<int:user_id>")
async def edit_user(user_id):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id, username, role FROM admins WHERE id = $1", user_id)

    if not user:
        flash("❌ User not found")
        return redirect(url_for("manage"))

    return await render_template("edit_user.html", user=user)

# --- Update User ---
@app.route("/update_user", methods=["POST"])
async def update_user():
    user_id = int(request.form["user_id"])
    username = request.form["username"]
    role = request.form["role"]

    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE admins SET username=$1, role=$2 WHERE id=$3",
            username, role, user_id
        )

    flash("✅ User updated successfully")
    return redirect(url_for("manage"))

# --- Approve Card ---
@app.route("/process_card", methods=["POST"])
async def process_card():
    card_id = request.form["card_id"]
    action = request.form["action"]

    async with db_pool.acquire() as conn:
        if action == "approved":
            card = await conn.fetchrow("SELECT * FROM pending_cards WHERE id = $1", card_id)
            await conn.execute("""
                INSERT INTO cards (code, character_name, form, image_url, description, event_name, created_at, approved)
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), TRUE)
            """, card["id"], card["character_name"], card["form"], card["image_url"], card["description"], card["event_name"])
            await conn.execute("DELETE FROM pending_cards WHERE id = $1", card_id)
            await conn.execute("INSERT INTO card_queue (card_id, action) VALUES ($1, 'add')", card["id"])
            flash(f"✅ Card {card['character_name']} approved")
        elif action == "rejected":
            await conn.execute("DELETE FROM pending_cards WHERE id = $1", card_id)
            flash(f"❌ Card {card_id} rejected and removed")

    return redirect(url_for("admin_dashboard"))

# --- Run Server ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 5000)), reload=True)
