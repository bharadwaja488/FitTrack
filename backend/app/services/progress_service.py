from datetime import timedelta


MAINTENANCE_TOLERANCE_KG = 0.5
COMPARISON_GRACE_DAYS = 7


def weight_change(records, days):
    """Compare the latest logged weight with a real record near the cutoff.

    A baseline is returned only when there is a measurement no more than seven
    days before the requested interval. Missing history stays unknown.
    """
    ordered = sorted(records, key=lambda row: row["recorded_at"])
    if len(ordered) < 2:
        return None
    latest = ordered[-1]
    cutoff = latest["recorded_at"] - timedelta(days=days)
    earliest_acceptable = cutoff - timedelta(days=COMPARISON_GRACE_DAYS)
    baseline = next(
        (row for row in reversed(ordered[:-1])
         if earliest_acceptable <= row["recorded_at"] <= cutoff),
        None,
    )
    if baseline is None:
        return None
    return float(latest["weight_kg"]) - float(baseline["weight_kg"])


def weight_trend(records):
    return {
        "weekly_weight_change_kg": weight_change(records, 7),
        "monthly_weight_change_kg": weight_change(records, 30),
        "history_count": len(records),
    }


def goal_progress(goal, current_weight, records):
    if not goal:
        return None

    starting = float(goal["starting_weight_kg"])
    target = float(goal["target_weight_kg"])
    current = float(current_weight)
    goal_type = goal["goal_type"]
    change = current - starting

    if goal_type == "weight_loss":
        total_lost = max(-change, 0.0)
        total_gained = max(change, 0.0)
        remaining = max(current - target, 0.0)
        percentage = min(100.0, max(0.0, (starting - current) / (starting - target) * 100))
        stability = None
    elif goal_type in {"weight_gain", "muscle_building"}:
        total_lost = max(-change, 0.0)
        total_gained = max(change, 0.0)
        remaining = max(target - current, 0.0)
        percentage = min(100.0, max(0.0, (current - starting) / (target - starting) * 100))
        stability = None
    else:
        total_lost = max(-change, 0.0)
        total_gained = max(change, 0.0)
        remaining = abs(current - target)
        percentage = None
        stability = "stable" if remaining <= MAINTENANCE_TOLERANCE_KG else (
            "above_target" if current > target else "below_target"
        )

    return {
        "starting_weight_kg": starting,
        "current_weight_kg": current,
        "target_weight_kg": target,
        "weight_change_kg": change,
        "total_weight_lost_kg": total_lost,
        "total_weight_gained_kg": total_gained,
        "remaining_to_target_kg": remaining,
        "progress_percentage": percentage,
        "maintenance_status": stability,
        **weight_trend(records),
    }
