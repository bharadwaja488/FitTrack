from datetime import date, datetime, time, timedelta

from flask import Blueprint, g, jsonify, request

from ..auth import login_required
from ..services.goal_service import create_or_update_goal, get_goal, update_goal_status
from ..services.weight_service import (
    add_weight_record,
    delete_weight_record,
    update_weight_record,
    weight_overview,
)
from ..utils.validators import body_json


bp = Blueprint("personal_goals", __name__)


def date_bounds():
    bounds = []
    for key, default in (("start", None), ("end", None)):
        value = request.args.get(key, "").strip()
        if not value:
            bounds.append(default)
            continue
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"{key.capitalize()} date must use YYYY-MM-DD format.")
        if parsed.isoformat() != value:
            raise ValueError(f"{key.capitalize()} date must use YYYY-MM-DD format.")
        bounds.append(datetime.combine(parsed, time.min) if key == "start" else datetime.combine(parsed + timedelta(days=1), time.min))
    if bounds[0] is not None and bounds[1] is not None and bounds[0] >= bounds[1]:
        raise ValueError("Start date must be on or before end date.")
    return tuple(bounds)


@bp.get("/goals")
@login_required
def goals():
    return jsonify({"data": get_goal(g.account["account_id"])})


@bp.put("/goals")
@login_required
def save_goal():
    result = create_or_update_goal(g.account["account_id"], body_json())
    if result is None:
        return jsonify({"error": {"code": "profile_required", "message": "Complete your profile before setting a goal."}}), 409
    return jsonify({"data": result})


@bp.patch("/goals/status")
@login_required
def goal_status():
    result = update_goal_status(g.account["account_id"], (request.get_json(silent=True) or {}).get("status"))
    if result is None:
        return jsonify({"error": {"code": "goal_not_found", "message": "No editable goal was found."}}), 404
    return jsonify({"data": result})


@bp.get("/weight")
@login_required
def weight_history():
    start, end = date_bounds()
    return jsonify({"data": weight_overview(g.account["account_id"], start, end)})


@bp.post("/weight")
@login_required
def create_weight():
    data = body_json()
    record = add_weight_record(g.account["account_id"], data.get("weight_kg"), data.get("recorded_at"))
    if record is None:
        return jsonify({"error": {"code": "profile_required", "message": "Complete your profile before logging weight."}}), 409
    return jsonify({"data": {"record": record}}), 201


@bp.put("/weight/<int:record_id>")
@login_required
def correct_weight(record_id):
    data = body_json()
    record = update_weight_record(g.account["account_id"], record_id, data.get("weight_kg"), data.get("recorded_at"))
    if record is False:
        return jsonify({"error": {"code": "weight_record_not_found", "message": "Weight record not found."}}), 404
    return jsonify({"data": {"record": record}})


@bp.delete("/weight/<int:record_id>")
@login_required
def remove_weight(record_id):
    if not delete_weight_record(g.account["account_id"], record_id):
        return jsonify({"error": {"code": "weight_record_not_found", "message": "Weight record not found."}}), 404
    return jsonify({"data": {"deleted": True}})
