from flask import Blueprint, g, jsonify, request, session
from ..auth import login_required
from ..services.account_service import change_password, delete_account

bp = Blueprint("settings", __name__)


@bp.put("/settings/password")
@login_required
def password():
    if not change_password(g.account["account_id"], request.get_json(silent=True) or {}):
        return jsonify({"error": {"code": "not_found", "message": "Account not found."}}), 404
    return jsonify({"data": {"password_updated": True}})


@bp.delete("/settings/account")
@login_required
def remove_account():
    data = request.get_json(silent=True) or {}
    if data.get("confirmation") != "DELETE":
        return jsonify({"error": {"code": "confirmation_required", "message": "Type DELETE to confirm account removal."}}), 400
    delete_account(g.account["account_id"], data.get("current_password", ""))
    session.clear()
    return jsonify({"data": {"deleted": True}})
