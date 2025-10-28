from quart import Blueprint, render_template, request, current_app
from utils.dashboard_data import dashboard_data

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/dashboard")
async def admin_dashboard():
    pool = current_app.config["DB_POOL"]
    stats = await dashboard_data(pool)
    return await render_template("admin_dashboard.html", stats=stats)

@admin_bp.route("/add", methods=["GET", "POST"])
async def add_card():
    return await render_template("add_card.html")

@admin_bp.route("/upload")
async def upload_image():
    return await render_template("upload_image.html")

@admin_bp.route("/history")
async def history():
    return await render_template("history.html")

@admin_bp.route("/edit")
async def edit_card_list():
    return await render_template("edit_card_list.html")

@admin_bp.route("/edit/<int:card_id>")
async def edit_card(card_id):
    return await render_template("edit_card.html", card_id=card_id)

@admin_bp.route("/edit/form/<int:card_id>")
async def edit_card_form(card_id):
    return await render_template("edit_card_form.html", card_id=card_id)

@admin_bp.route("/search")
async def search_player():
    return await render_template("search_player.html")

@admin_bp.route("/profile/<int:player_id>")
async def profile(player_id):
    return await render_template("profile.html", player_id=player_id)

@admin_bp.route("/player_not_found")
async def player_not_found():
    return await render_template("player_not_found.html")

@admin_bp.route("/review")
async def review_submissions():
    return await render_template("review_submissions.html")

@admin_bp.route("/submit", methods=["GET", "POST"])
async def submit_card():
    return await render_template("submit_card.html")

@admin_bp.route("/manage")
async def manage():
    return await render_template("manage.html")

@admin_bp.route("/edit/user/<int:user_id>")
async def edit_user(user_id):
    return await render_template("edit_user.html", user_id=user_id)

# Form actions
@admin_bp.route("/delete", methods=["POST"])
async def delete_card():
    form = await request.form
    card_id = form.get("card_id")
    # TODO: delete logic
    return f"Deleted card {card_id}"

@admin_bp.route("/process", methods=["POST"])
async def process_card():
    form = await request.form
    card_id = form.get("card_id")
    action = form.get("action")
    # TODO: process logic
    return f"{action.capitalize()} card {card_id}"

@admin_bp.route("/remove_card", methods=["POST"])
async def remove_card_from_player():
    form = await request.form
    card_id = form.get("card_id")
    discord_id = form.get("discord_id")
    # TODO: removal logic
    return f"Removed card {card_id} from {discord_id}"

@admin_bp.route("/assign_card", methods=["POST"])
async def add_card_to_player():
    form = await request.form
    card_id = form.get("card_id")
    discord_id = form.get("discord_id")
    # TODO: assign logic
    return f"Assigned card {card_id} to {discord_id}"
