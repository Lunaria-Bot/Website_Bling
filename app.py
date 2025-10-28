from quart import Quart, render_template, session
from authy import authy
from admin import admin_bp
from player import player_bp
from db import init_db, db_pool

import os

app = Quart(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ["SECRET_KEY"]

# Register blueprints
app.register_blueprint(authy)
app.register_blueprint(admin_bp)
app.register_blueprint(player_bp)

@app.before_serving
async def startup():
    await init_db()
    player_bp.db_pool = db_pool  # inject pool into player
    admin_bp.db_pool = db_pool   # optional: if admin needs DB

@app.route("/")
async def home():
    return await render_template("base.html")

if __name__ == "__main__":
    app.run(debug=True)
