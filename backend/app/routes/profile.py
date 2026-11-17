from flask import Blueprint, g, jsonify
from ..auth import login_required
from ..services.profile_service import get_profile, save_profile
from ..utils.validators import body_json, profile_values

bp = Blueprint("profile", __name__)


@bp.get("/profile")
@login_required
def profile():
    return jsonify({"data": {"profile": get_profile(g.account["account_id"])}})


@bp.put("/profile")
@login_required
def update_profile():
    profile = save_profile(g.account["account_id"], profile_values(body_json()))
    return jsonify({"data": {"profile": profile}})
