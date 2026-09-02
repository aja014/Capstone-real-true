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
