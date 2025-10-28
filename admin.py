from quart import Blueprint, render_template
admin = Blueprint("admin", __name__)

@admin.route("/dashboard")
async def admin_dashboard():
    return await render_template("admin_dashboard.html")

@admin.route("/add")
async def add_card():
    return await render_template("add_card.html")

@admin.route("/history")
async def history():
    return await render_template("history.html")

@admin.route("/edit")
async def edit_card_list():
    return await render_template("edit_card_list.html")

@admin.route("/search")
async def search_player():
    return await render_template("search_player.html")

@admin.route("/manage")
async def manage():
    return await render_template("manage.html")
