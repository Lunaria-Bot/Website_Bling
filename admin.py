from quart import Blueprint, render_template

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/dashboard")
async def admin_dashboard():
    return await render_template("admin_dashboard.html")

@admin_bp.route("/add")
async def add_card():
    return await render_template("add_card.html")

@admin_bp.route("/history")
async def history():
    return await render_template("history.html")

@admin_bp.route("/edit")
async def edit_card_list():
    return await render_template("edit_card_list.html")

@admin_bp.route("/search")
async def search_player():
    return await render_template("search_player.html")

@admin_bp.route("/manage")
async def manage():
    return await render_template("manage.html")
