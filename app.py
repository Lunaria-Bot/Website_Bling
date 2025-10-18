from flask import Flask, render_template, request, redirect, url_for, flash
import asyncpg
import asyncio

app = Flask(__name__)
app.secret_key = "supersecret"  # for flash messages

# Database connection pool
async def init_db():
    return await asyncpg.create_pool(
        user="postgres",
        password="yourpassword",
        database="yourdb",
        host="localhost"
    )

loop = asyncio.get_event_loop()
db_pool = loop.run_until_complete(init_db())

@app.route("/add_card", methods=["GET", "POST"])
def add_card():
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

