from datetime import date
from flask import Blueprint, g, jsonify, request

from ..auth import login_required
from ..services.personal_fitness_service import (
    add_record, delete_record, get_step_goal, list_records, set_step_goal, update_record,
)
from ..utils.validators import body_json, record_values, step_goal_value

bp = Blueprint("personal_fitness", __name__)


def date_filter(key):
    value = request.args.get(key, "").strip()
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{key.capitalize()} date must use YYYY-MM-DD format.")
    if parsed.isoformat() != value:
        raise ValueError(f"{key.capitalize()} date must use YYYY-MM-DD format.")
    return parsed


def records():
    start, end = date_filter("start"), date_filter("end")
    if start and end and start > end:
        raise ValueError("Start date must be on or before end date.")
    return list_records(g.account["account_id"], start, end)


@bp.get("/fitness")
@login_required
def fitness():
    return jsonify({"data": records()})


@bp.get("/fitness/history")
@login_required
def history():
    return jsonify({"data": records()})


@bp.post("/fitness")
@login_required
def create_fitness():
    record = add_record(g.account["account_id"], record_values(body_json()))
    if not record:
        return jsonify({"error": {"code": "onboarding_required", "message": "Complete your profile before tracking activity."}}), 409
    return jsonify({"data": record}), 201


@bp.put("/fitness/<int:record_id>")
@login_required
def edit_fitness(record_id):
    record = update_record(g.account["account_id"], record_id, record_values(body_json()))
    if not record:
        return jsonify({"error": {"code": "fitness_record_not_found", "message": "Activity record not found."}}), 404
    return jsonify({"data": record})


@bp.delete("/fitness/<int:record_id>")
@login_required
def remove_fitness(record_id):
    if not delete_record(g.account["account_id"], record_id):
        return jsonify({"error": {"code": "fitness_record_not_found", "message": "Activity record not found."}}), 404
    return jsonify({"data": {"deleted": True}})


@bp.get("/fitness/step-goal")
@login_required
def read_step_goal():
    return jsonify({"data": {"daily_step_goal": get_step_goal(g.account["account_id"])}})


@bp.put("/fitness/step-goal")
@login_required
def write_step_goal():
    step_goal = set_step_goal(g.account["account_id"], step_goal_value(body_json()))
    if step_goal is None:
        return jsonify({"error": {"code": "profile_required", "message": "Complete your profile before setting an activity goal."}}), 409
    return jsonify({"data": {"daily_step_goal": step_goal}})
