import os
import asyncio
import asyncpg
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

loop = asyncio.get_event_loop()
db_pool = None

async def init_db():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return await asyncpg.create_pool(dsn=db_url, ssl="require")
    else:
        return await asyncpg.create_pool(
            user="postgres",
            password="yourpassword",
            database="yourdb",
            host="127.0.0.1",
            port=5432
        )

db_pool = loop.run_until_complete(init_db())

# --- Authentication ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form["password"]
        if password == os.getenv("ADMIN_PASSWORD", "changeme"):
            session["logged_in"] = True
            flash("✅ Logged in successfully!")
            return redirect(url_for("add_card"))
        else:
            flash("❌ Wrong password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("login"))

# --- Card form ---
@app.route("/", methods=["GET", "POST"])
def add_card():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        base_name = request.form["base_name"]
        description = request.form["description"]

        rarities = ["common", "rare", "epic", "legendary"]
        potentials = [1, 2, 3, 4]

        async def insert_cards():
            async with db_pool.acquire() as conn:
                for rarity, potential in zip(rarities, potentials):
                    name = f"{base_name} ({rarity.capitalize()})"
                    image_url = request.form[f"image_{rarity}"]
                    await conn.execute("""
                        INSERT INTO cards (base_name, name, rarity, potential, image_url, description)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """, base_name, name, rarity, potential, image_url, description)

        loop.run_until_complete(insert_cards())
        flash("✅ All rarities added successfully!")
        return redirect(url_for("add_card"))

    return render_template("add_card.html")

# --- History page with filters ---
@app.route("/history")
def history():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    rarity_filter = request.args.get("rarity")
    search = request.args.get("search")

    async def fetch_cards():
        async with db_pool.acquire() as conn:
            query = """
                SELECT base_name, name, rarity, potential, image_url, description, created_at
                FROM cards
            """
            conditions = []
            params = []
            if rarity_filter and rarity_filter != "all":
                conditions.append("rarity = $%d" % (len(params)+1))
                params.append(rarity_filter)
            if search:
                conditions.append("base_name ILIKE $%d" % (len(params)+1))
                params.append(f"%{search}%")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC LIMIT 50"
            return await conn.fetch(query, *params)

    cards = loop.run_until_complete(fetch_cards())
    return render_template("history.html", cards=cards, rarity_filter=rarity_filter, search=search)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
