from quart import Blueprint, render_template, session, redirect, url_for

admin_bp = Blueprint("admin", __name__)

def require_admin():
    if not session.get("is_admin"):
        return redirect(url_for("home"))

@admin_bp.route("/admin/dashboard")
async def admin_dashboard():
    if not session.get("is_admin"):
        return redirect(url_for("home"))
    return await render_template("admin/dashboard.html")

@admin_bp.route("/admin/add_card")
async def add_card():
    if not session.get("is_admin"):
        return redirect(url_for("home"))
    return await render_template("admin/add_card.html")

@admin_bp.route("/admin/edit_card_list")
async def edit_card_list():
    if not session.get("is_admin"):
        return redirect(url_for("home"))
    return await render_template("admin/edit_card_list.html")

@admin_bp.route("/admin/search_player")
async def search_player():
    if not session.get("is_admin"):
        return redirect(url_for("home"))
    return await render_template("admin/search_player.html")

@admin_bp.route("/admin/manage")
async def manage():
    if not session.get("is_admin"):
        return redirect(url_for("home"))
    return await render_template("admin/manage.html")
