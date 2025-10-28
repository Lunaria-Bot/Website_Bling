import os
import asyncpg
from quart import Quart, render_template, session
from authy import authy
from admin import admin_bp
from player import player_bp

app = Quart(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-key")

# PostgreSQL config (Railway)
DATABASE_URL = "postgresql://postgres:ZGCrcbXKKjCIudreaDNqhjagjvfEOIFa@postgres.railway.internal:5432/railway"

# Global pool reference
db_pool = None

@app.before_serving
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=5
    )
    # Inject pool into blueprints
    player_bp.db_pool = db_pool
    admin_bp.db_pool = db_pool

@app.after_serving
async def shutdown():
    await db_pool.close()

# Register blueprints
app.register_blueprint(authy)
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(player_bp, url_prefix="/player")

@app.route("/")
async def home():
    return await render_template("base.html")

if __name__ == "__main__":
    app.run(debug=True)
