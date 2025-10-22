import os
import asyncpg
import uuid
from quart import Quart, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import check_password_hash

app = Quart(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

db_pool = None

@app.before_serving
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(
        dsn=os.getenv("DATABASE_URL"),
        ssl="require"
    )

# --- Root Route ---
@app.route("/")
async def home():
    return redirect(url_for("login"))

# --- Login ---
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

        if admin:
            print("Fetched admin:", dict(admin))
        else:
            print("No admin found for username:", username)

        if admin and check_password_hash(admin["password_hash"], password):
            session["user_id"] = admin["id"]
            session["username"] = admin["username"]
            session["role"] = admin["role"]
            print("Session set:", dict(session))
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
# --- Admin Dashboard ---
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
            SELECT id, character_name, form, image_url, description, created_at
            FROM cards ORDER BY created_at DESC LIMIT 5
        """)
        pending = await conn.fetch("""
            SELECT id, title, description, image_url, submitted_by, form_type, created_at
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
            form = await request.form
            name = form["character_name"]
            form_type = form["form"]
            image_url = form["image_url"]
            description = form["description"]

            await conn.execute("""
                UPDATE cards
                SET character_name = $1,
                    form = $2,
                    image_url = $3,
                    description = $4
                WHERE id = $5
            """, name, form_type, image_url, description, card_id)

            return redirect(url_for("edit_card_list"))

    return await render_template("edit_card_form.html", card=card)
 # --- ADD Card ---   
 @app.route("/add_card", methods=["GET", "POST"])
async def add_card():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":
        form = await request.form
        name = form["base_name"]
        form_type = form["form"]
        description = form["description"]
        image_url = form["image_url"]

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO cards (character_name, form, description, image_url, created_at)
                VALUES ($1, $2, $3, $4, NOW())
            """, name, form_type, description, image_url)

        await flash(f"✅ Card '{name}' added successfully!")
        return redirect(url_for("admin_dashboard"))

    return await render_template("add_card.html")
   

# --- Delete Card ---
@app.route("/delete_card", methods=["POST"])
async def delete_card():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    form = await request.form
    card_id = int(form.get("card_id"))
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

    form = await request.form
    player_id = int(form.get("player_id"))
    card_id = int(form.get("card_id"))
    discord_id = form.get("discord_id")

    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE cards SET owner_id=$1 WHERE id=$2", player_id, card_id)

    flash("✅ Card assigned to player!")
    return redirect(url_for("player_profile", discord_id=discord_id))

# --- Remove Card from Player ---
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

# --- Search Player ---
@app.route("/search_player", methods=["GET", "POST"])
async def search_player():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        form = await request.form
        discord_id = form.get("discord_id").strip()
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

# --- Approve Card ---
@app.route("/process_card", methods=["POST"])
async def process_card():
    form = await request.form
    card_id = form["card_id"]
    action = form["action"]

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
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
