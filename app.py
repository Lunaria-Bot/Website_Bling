import os
import asyncio
import asyncpg
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")  # change in Railway vars

loop = asyncio.get_event_loop()
db_pool = None

async def init_db():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Railway provides DATABASE_URL
        return await asyncpg.create_pool(dsn=db_url, ssl="require")
    else:
        # Local fallback
        return await asyncpg.create_pool(
            user="postgres",
            password="yourpassword",
            database="yourdb",
            host="127.0.0.1",
            port=5432
        )

# Initialize pool at startup
db_pool = loop.run_until_complete(init_db())

@app.route("/", methods=["GET", "POST"])
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
