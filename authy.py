from quart import Blueprint, redirect, request, session, url_for
import os
import httpx

authy = Blueprint("authy", __name__)

DISCORD_CLIENT_ID = os.environ["DISCORD_CLIENT_ID"]
DISCORD_CLIENT_SECRET = os.environ["DISCORD_CLIENT_SECRET"]
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "https://yourdomain.com/callback")
ADMIN_IDS = [912376040142307419]

DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api/users/@me"

@authy.route("/login")
async def login():
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify"
    }
    query = "&".join([f"{k}={v}" for k, v in params.items()])
    return redirect(f"{DISCORD_AUTH_URL}?{query}")

@authy.route("/callback")
async def callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(DISCORD_TOKEN_URL, data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_REDIRECT_URI,
            "scope": "identify"
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return "Token fetch failed", 400

        user_resp = await client.get(DISCORD_API_URL, headers={
            "Authorization": f"Bearer {access_token}"
        })
        profile = user_resp.json()

    session["discord_id"] = int(profile["id"])
    session["username"] = profile["username"]
    session["avatar_url"] = f"https://cdn.discordapp.com/avatars/{profile['id']}/{profile['avatar']}.png"
    session["is_admin"] = int(profile["id"]) in ADMIN_IDS

    return redirect(url_for("home"))

@authy.route("/logout")
async def logout():
    session.clear()
    return redirect(url_for("home"))
