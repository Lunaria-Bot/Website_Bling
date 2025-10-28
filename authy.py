from quart import Blueprint, redirect, request, session, url_for
from authlib.integrations.quart_client import OAuth
import os

authy = Blueprint("authy", __name__)
oauth = OAuth()

DISCORD_CLIENT_ID = os.environ["DISCORD_CLIENT_ID"]
DISCORD_CLIENT_SECRET = os.environ["DISCORD_CLIENT_SECRET"]
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "https://yourdomain.com/callback")

oauth.register(
    name="discord",
    client_id=DISCORD_CLIENT_ID,
    client_secret=DISCORD_CLIENT_SECRET,
    access_token_url="https://discord.com/api/oauth2/token",
    authorize_url="https://discord.com/oauth2/authorize",
    api_base_url="https://discord.com/api/",
    client_kwargs={"scope": "identify"},
)

ADMIN_IDS = [912376040142307419]  # Remplace par tes vrais IDs Discord admin

@authy.route("/login")
async def login():
    discord = oauth.create_client("discord")
    return await discord.authorize_redirect(DISCORD_REDIRECT_URI)

@authy.route("/callback")
async def callback():
    discord = oauth.create_client("discord")
    token = await discord.authorize_access_token()
    user = await discord.get("users/@me")
    profile = user.json()

    session["discord_id"] = int(profile["id"])
    session["username"] = profile["username"]
    session["avatar_url"] = f"https://cdn.discordapp.com/avatars/{profile['id']}/{profile['avatar']}.png"
    session["is_admin"] = int(profile["id"]) in ADMIN_IDS

    return redirect(url_for("home"))

@authy.route("/logout")
async def logout():
    session.clear()
    return redirect(url_for("home"))
