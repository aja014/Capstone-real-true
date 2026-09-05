import calendar
from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.security import get_current_user
from app import models, schemas

router = APIRouter(
    prefix="/stats",
    tags=["Stats"],
    dependencies=[Depends(get_current_user)],
)

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _is_renewed(renewing_policy_no) -> bool:
    return bool(renewing_policy_no and renewing_policy_no.strip())


def _range_for_period(period: str, ref_date: date_type) -> tuple[date_type, date_type]:
    if period == "daily":
        return ref_date, ref_date
    if period == "mtd":
        # 1st of the month through the given date — NOT the whole month,
        # so days after `ref_date` (still in the future relative to it)
        # never show data.
        return ref_date.replace(day=1), ref_date
    # ytd: Jan 1 through the exact given date — same "as of" cutoff
    # philosophy as MTD, so the two periods never disagree about what
    # "as of `ref_date`" means. The current month's bar is deliberately
    # partial early in the month (not padded out to month-end).
    return ref_date.replace(month=1, day=1), ref_date


@router.get("/policy-distribution", response_model=schemas.PolicyDistributionStats)
def get_policy_distribution(
    period: Literal["daily", "mtd", "ytd"] = Query(...),
    date: date_type = Query(...),
    db: Session = Depends(get_db),
):
    range_start, range_end = _range_for_period(period, date)

    fire_policies = db.query(models.FirePropertyPolicy).filter(
        models.FirePropertyPolicy.issue_date >= range_start,
        models.FirePropertyPolicy.issue_date <= range_end,
    ).all()
    motor_policies = db.query(models.MotorPolicy).filter(
        models.MotorPolicy.issue_date >= range_start,
        models.MotorPolicy.issue_date <= range_end,
    ).all()

    total_amount_due = sum(
        (p.total_amount_due or 0) for p in fire_policies + motor_policies
    )

    bar_chart: list[dict] = []
    fire_pie: list[dict] = []
    motor_pie: list[dict] = []

    if period in ("mtd", "ytd"):
        fire_pie = [
            {"name": "New Policy", "value": sum(1 for p in fire_policies if not _is_renewed(p.renewing_policy_no))},
            {"name": "Renewed Policy", "value": sum(1 for p in fire_policies if _is_renewed(p.renewing_policy_no))},
        ]
        motor_pie = [
            {"name": "New Policy", "value": sum(1 for p in motor_policies if not _is_renewed(p.renewing_policy_no))},
            {"name": "Renewed Policy", "value": sum(1 for p in motor_policies if _is_renewed(p.renewing_policy_no))},
        ]

        if period == "mtd":
            buckets = {d: {"fire": 0, "motor": 0} for d in range(1, range_end.day + 1)}
            for p in fire_policies:
                buckets[p.issue_date.day]["fire"] += 1
            for p in motor_policies:
                buckets[p.issue_date.day]["motor"] += 1
            bar_chart = [
                {"label": str(d), "fire_count": buckets[d]["fire"], "motor_count": buckets[d]["motor"]}
                for d in sorted(buckets)
            ]
        else:  # ytd
            buckets = {m: {"fire": 0, "motor": 0} for m in range(1, range_end.month + 1)}
            for p in fire_policies:
                buckets[p.issue_date.month]["fire"] += 1
            for p in motor_policies:
                buckets[p.issue_date.month]["motor"] += 1
            bar_chart = [
                {"label": MONTH_NAMES[m - 1], "fire_count": buckets[m]["fire"], "motor_count": buckets[m]["motor"]}
                for m in sorted(buckets)
            ]

    return {
        "period": period,
        "date": date,
        "range_start": range_start,
        "range_end": range_end,
        "total_policies": len(fire_policies) + len(motor_policies),
        "fire_count": len(fire_policies),
        "motor_count": len(motor_policies),
        "total_amount_due": total_amount_due,
        "bar_chart": bar_chart,
        "fire_pie": fire_pie,
        "motor_pie": motor_pie,
    }


# ------------------------------------------------------------
# RENEWAL RATIO MONITORING (Objective 1.4 groundwork)
# ------------------------------------------------------------

def _expiry_range_for_period(period: str, ref_date: date_type) -> tuple[date_type, date_type]:
    # Deliberately NOT cut off at ref_date like _range_for_period above —
    # a policy's expiry (period_to) is an already-fixed fact set when the
    # policy was created, not something that "hasn't happened yet" the way
    # an issue date would be. MTD/YTD here cover the WHOLE current
    # month/year, future-dated expiries included.
    if period == "daily":
        return ref_date, ref_date
    if period == "mtd":
        last_day = calendar.monthrange(ref_date.year, ref_date.month)[1]
        return ref_date.replace(day=1), ref_date.replace(day=last_day)
    return ref_date.replace(month=1, day=1), ref_date.replace(month=12, day=31)  # ytd


def _renewal_status(policy, renewer_target_ids: dict, ref_date: date_type) -> str:
    """
    Each policy evaluated independently. Only 3 states — no more "New":
    - Renewed: some OTHER policy in the same line has renewing_policy_no
      equal to this policy's policy_no (checked regardless of this
      policy's own expiry — a renewed policy can itself later become
      Pending/Lost/Renewed again as ITS expiry approaches).
    - Otherwise: Lost if expiry has already passed, Pending if it hasn't
      (no day-count window — a policy 300 days from expiry is Pending
      just like one 5 days out).

    A policy with no period_to on file can still land here (this is
    called against ALL policies, not just ones in the selected period)
    but the caller's in_range() filter always excludes it from output,
    so the "Pending" fallback below is never actually surfaced.
    """
    pno = (policy.policy_no or "").strip()
    renewer_ids = renewer_target_ids.get(pno, []) if pno else []
    if any(rid != policy.id for rid in renewer_ids):
        return "Renewed"
    if policy.period_to and ref_date > policy.period_to:
        return "Lost"
    return "Pending"


def _compute_statuses(policies: list, ref_date: date_type) -> dict:
    # Same-line-only matching: only policies from the SAME list (Fire or
    # Motor, never mixed) ever count as "renewing" one another.
    renewer_target_ids: dict[str, list[int]] = {}
    for p in policies:
        target = (p.renewing_policy_no or "").strip()
        if target:
            renewer_target_ids.setdefault(target, []).append(p.id)
    return {p.id: _renewal_status(p, renewer_target_ids, ref_date) for p in policies}


def _client_name(insurance_case) -> str:
    policyholder = insurance_case.policyholder if insurance_case else None
    if not policyholder:
        return "—"
    parts = [policyholder.first_name, policyholder.middle_name, policyholder.last_name]
    return " ".join(p for p in parts if p) or "—"


@router.get("/renewal-ratio", response_model=schemas.RenewalRatioStats)
def get_renewal_ratio(
    period: Literal["daily", "mtd", "ytd"] = Query(...),
    date: date_type = Query(...),
    db: Session = Depends(get_db),
):
    range_start, range_end = _expiry_range_for_period(period, date)

    # Status ("Renewed" in particular) must be computed against ALL
    # policies in the line, not just ones in the selected period — a
    # policy issued/expiring far outside this window can still be the one
    # that renews a policy whose expiry DOES fall in range.
    fire_policies = db.query(models.FirePropertyPolicy).all()
    motor_policies = db.query(models.MotorPolicy).all()

    fire_statuses = _compute_statuses(fire_policies, date)
    motor_statuses = _compute_statuses(motor_policies, date)

    def in_range(p):
        return p.period_to is not None and range_start <= p.period_to <= range_end

    fire_rows = [(p, fire_statuses[p.id], "Fire & Property") for p in fire_policies if in_range(p)]
    motor_rows = [(p, motor_statuses[p.id], "Motor Car") for p in motor_policies if in_range(p)]
    combined = fire_rows + motor_rows

    def line_counts(rows):
        renewed = sum(1 for _, s, _ in rows if s == "Renewed")
        lost = sum(1 for _, s, _ in rows if s == "Lost")
        pending = sum(1 for _, s, _ in rows if s == "Pending")
        return renewed, lost, pending

    fire_renewed, fire_lost, fire_pending = line_counts(fire_rows)
    motor_renewed, motor_lost, motor_pending = line_counts(motor_rows)

    renewed_count = fire_renewed + motor_renewed
    lost_count = fire_lost + motor_lost
    pending_count = fire_pending + motor_pending
    expiring_count = renewed_count + lost_count + pending_count
    renewal_rate = (renewed_count / expiring_count * 100) if expiring_count else 0.0

    fire_pie = [
        {"name": "Renewed Policy", "value": fire_renewed},
        {"name": "Lost Policy", "value": fire_lost},
        {"name": "Pending", "value": fire_pending},
    ]
    motor_pie = [
        {"name": "Renewed Policy", "value": motor_renewed},
        {"name": "Lost Policy", "value": motor_lost},
        {"name": "Pending", "value": motor_pending},
    ]

    bar_chart: list[dict] = []
    if period == "mtd":
        buckets = {d: {"renewed": 0, "lost": 0, "pending": 0} for d in range(1, range_end.day + 1)}
        for p, status, _line in combined:
            buckets[p.period_to.day][status.lower()] += 1
        bar_chart = [
            {"label": str(d), "renewed_count": b["renewed"], "lost_count": b["lost"], "pending_count": b["pending"]}
            for d, b in sorted(buckets.items())
        ]
    elif period == "ytd":
        buckets = {m: {"renewed": 0, "lost": 0, "pending": 0} for m in range(1, 13)}
        for p, status, _line in combined:
            buckets[p.period_to.month][status.lower()] += 1
        bar_chart = [
            {"label": MONTH_NAMES[m - 1], "renewed_count": b["renewed"], "lost_count": b["lost"], "pending_count": b["pending"]}
            for m, b in sorted(buckets.items())
        ]

    policy_rows = [
        {
            "id": p.id,
            "policy_no": p.policy_no,
            "client_name": _client_name(p.quotation.insurance_case if p.quotation else None),
            "line": line,
            "issue_date": p.issue_date,
            "expiry_date": p.period_to,
            "total_amount_due": p.total_amount_due,
            "sum_insured": p.sum_insured if line == "Fire & Property" else None,
            "status": status,
        }
        for p, status, line in combined
    ]

    return {
        "period": period,
        "date": date,
        "range_start": range_start,
        "range_end": range_end,
        "expiring_count": expiring_count,
        "renewed_count": renewed_count,
        "lost_count": lost_count,
        "pending_count": pending_count,
        "renewal_rate": renewal_rate,
        "bar_chart": bar_chart,
        "fire_pie": fire_pie,
        "motor_pie": motor_pie,
        "policies": policy_rows,
    }
