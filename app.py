from quart import Quart, render_template, session
from auth import auth_bp
from player import player_bp
from admin import admin_bp
import os
from dotenv import load_dotenv

load_dotenv()

app = Quart(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "warp-gate-secret")

# Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(player_bp)
app.register_blueprint(admin_bp)

@app.route("/")
async def home():
    return await render_template("base.html")

if __name__ == "__main__":
    app.run(debug=True)
