from flask import Blueprint, g, jsonify, request
from ..auth import login_required
from ..services.personal_fitness_service import dashboard_activity, dashboard_summary

bp = Blueprint("personal_dashboard", __name__)


@bp.get("/dashboard/summary")
@login_required
def summary():
    return jsonify({"data": dashboard_summary(g.account["account_id"])})


@bp.get("/dashboard/activity")
@login_required
def activity():
    return jsonify({"data": dashboard_activity(g.account["account_id"], request.args.get("period", "week"))})
