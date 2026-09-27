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
MONTH_ABBR = [n[:3] for n in MONTH_NAMES]


def _is_renewed(renewing_policy_no) -> bool:
    return bool(renewing_policy_no and renewing_policy_no.strip())


def _range_for_period(period: str, ref_date: date_type) -> tuple[date_type, date_type]:
    if period == "daily":
        return ref_date, ref_date
    if period == "mtd":
        # 1st of the month through either today (the current month — never
        # show days that haven't happened yet) or the full last day of the
        # month (any other, i.e. past, month — nothing left to cut off).
        today = date_type.today()
        start = ref_date.replace(day=1)
        if ref_date.year == today.year and ref_date.month == today.month:
            end = today
        else:
            last_day = calendar.monthrange(ref_date.year, ref_date.month)[1]
            end = ref_date.replace(day=last_day)
        return start, end
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

    # Renewed/Lost/Pending is always judged against the REAL current date,
    # never against `date` (which, for MTD, may now be a past month the
    # user explicitly picked to browse) — a policy overdue since July must
    # still read Lost today even while viewing July's window, not Pending
    # "as of July 1".
    today = date_type.today()
    fire_statuses = _compute_statuses(fire_policies, today)
    motor_statuses = _compute_statuses(motor_policies, today)

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
    # Pending (not expired yet, not renewed yet) has no outcome yet, so it's left out
    # of the rate — otherwise every future expiry drags the rate down as "not renewed".
    decided_count = renewed_count + lost_count
    renewal_rate = (renewed_count / decided_count * 100) if decided_count else 0.0

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
            "sum_insured": p.sum_insured,
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


# ------------------------------------------------------------
# OVERVIEW DASHBOARD (fixed dashboard, no period selector — combines
# this-month totals, a last-4-calendar-years bar, and a rolling 6-month
# line in one response since the frontend needs all of it for one view)
# ------------------------------------------------------------

def _month_bounds(year: int, month: int) -> tuple[date_type, date_type]:
    last_day = calendar.monthrange(year, month)[1]
    return date_type(year, month, 1), date_type(year, month, last_day)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


@router.get("/overview", response_model=schemas.OverviewStats)
def get_overview(db: Session = Depends(get_db)):
    today = date_type.today()
    month_start, month_end = _month_bounds(today.year, today.month)

    fire_policies_month = db.query(models.FirePropertyPolicy).filter(
        models.FirePropertyPolicy.issue_date >= month_start,
        models.FirePropertyPolicy.issue_date <= month_end,
    ).all()
    motor_policies_month = db.query(models.MotorPolicy).filter(
        models.MotorPolicy.issue_date >= month_start,
        models.MotorPolicy.issue_date <= month_end,
    ).all()

    gross_premium_written = sum(
        (p.total_amount_due or 0) for p in fire_policies_month + motor_policies_month
    )
    policies_made = len(fire_policies_month) + len(motor_policies_month)

    fire_quotations_month = db.query(models.FirePropertyQuotation).filter(
        models.FirePropertyQuotation.quotation_date >= month_start,
        models.FirePropertyQuotation.quotation_date <= month_end,
    ).all()
    motor_quotations_month = db.query(models.MotorQuotation).filter(
        models.MotorQuotation.quotation_date >= month_start,
        models.MotorQuotation.quotation_date <= month_end,
    ).all()

    quotations_offered = len(fire_quotations_month) + len(motor_quotations_month)

    # Filed Claims card: same "this month" basis as quotations_offered --
    # claims (both lines) whose date_reported falls in the current month.
    filed_claims = db.query(models.MotorClaim).filter(
        models.MotorClaim.date_reported >= month_start,
        models.MotorClaim.date_reported <= month_end,
    ).count() + db.query(models.FirePropertyClaim).filter(
        models.FirePropertyClaim.date_reported >= month_start,
        models.FirePropertyClaim.date_reported <= month_end,
    ).count()

    # Quotation vs. Converted Accounts pie: rolling 3-month window ending at
    # the current month (not calendar-year aligned), same rolling-window
    # philosophy as monthly_line's 6-month window below — deliberately a
    # DIFFERENT scope than `quotations_offered` above, which stays
    # current-month-only per the stat card's own "this month" framing.
    pie_start_year, pie_start_month = _shift_month(today.year, today.month, -2)
    pie_range_start, _ = _month_bounds(pie_start_year, pie_start_month)

    fire_quotations_3mo = db.query(models.FirePropertyQuotation).filter(
        models.FirePropertyQuotation.quotation_date >= pie_range_start,
        models.FirePropertyQuotation.quotation_date <= month_end,
    ).all()
    motor_quotations_3mo = db.query(models.MotorQuotation).filter(
        models.MotorQuotation.quotation_date >= pie_range_start,
        models.MotorQuotation.quotation_date <= month_end,
    ).all()

    pie_quotations_offered = len(fire_quotations_3mo) + len(motor_quotations_3mo)
    pie_converted = sum(1 for q in fire_quotations_3mo if q.policy is not None) + sum(
        1 for q in motor_quotations_3mo if q.policy is not None
    )
    quotation_pie = [
        {"name": "Converted", "value": pie_converted},
        {"name": "Quotation", "value": pie_quotations_offered - pie_converted},
    ]
    if pie_start_year == today.year:
        quotation_pie_label = f"Past 3 Months ({MONTH_ABBR[pie_start_month - 1]}-{MONTH_ABBR[today.month - 1]} {today.year})"
    else:
        quotation_pie_label = (
            f"Past 3 Months ({MONTH_ABBR[pie_start_month - 1]} {pie_start_year}"
            f"-{MONTH_ABBR[today.month - 1]} {today.year})"
        )

    # Last 4 calendar years including the current one, oldest first.
    years = [today.year - 3, today.year - 2, today.year - 1, today.year]
    yearly_bar = []
    for year in years:
        fire_count = db.query(models.FirePropertyPolicy).filter(
            models.FirePropertyPolicy.issue_date >= date_type(year, 1, 1),
            models.FirePropertyPolicy.issue_date <= date_type(year, 12, 31),
        ).count()
        motor_count = db.query(models.MotorPolicy).filter(
            models.MotorPolicy.issue_date >= date_type(year, 1, 1),
            models.MotorPolicy.issue_date <= date_type(year, 12, 31),
        ).count()
        yearly_bar.append({"label": str(year), "fire_count": fire_count, "motor_count": motor_count})

    # Rolling 6-month window ending at the current month, oldest first —
    # NOT calendar-year aligned (e.g. April..September if today is in
    # September), unlike the YTD-style bucketing used elsewhere in this file.
    monthly_line = []
    for delta in range(-5, 1):
        y, m = _shift_month(today.year, today.month, delta)
        m_start, m_end = _month_bounds(y, m)
        fire_count = db.query(models.FirePropertyPolicy).filter(
            models.FirePropertyPolicy.issue_date >= m_start,
            models.FirePropertyPolicy.issue_date <= m_end,
        ).count()
        motor_count = db.query(models.MotorPolicy).filter(
            models.MotorPolicy.issue_date >= m_start,
            models.MotorPolicy.issue_date <= m_end,
        ).count()
        monthly_line.append({"label": MONTH_ABBR[m - 1], "fire_count": fire_count, "motor_count": motor_count})

    return {
        "date": today,
        "month_label": f"{MONTH_NAMES[today.month - 1]} {today.year}",
        "gross_premium_written": gross_premium_written,
        "policies_made": policies_made,
        "quotations_offered": quotations_offered,
        "filed_claims": filed_claims,
        "quotation_pie": quotation_pie,
        "quotation_pie_label": quotation_pie_label,
        "yearly_bar": yearly_bar,
        "monthly_line": monthly_line,
    }


# ------------------------------------------------------------
# QUOTATIONS / PROPOSAL PAGE (KPI cards + per-line pies + trend chart —
# the page's own quotation TABLE reuses the existing per-quotation REST
# endpoints/join logic instead, see Frontend/src/lib/quotations.js)
# ------------------------------------------------------------

@router.get("/quotation-proposal", response_model=schemas.QuotationProposalStats)
def get_quotation_proposal_stats(
    # Literal[3, 6, 12] rejects a numeric query string like "3" outright in
    # this FastAPI/pydantic version (no int coercion before the literal
    # check) -- validated by hand instead, same 3 allowed values.
    months: int = Query(6),
    # Both must be supplied to activate "specific month" mode; a partial or
    # invalid pair silently falls back to rolling mode, same "invalid ->
    # default" convention as `months` above.
    year: int | None = Query(None),
    month: int | None = Query(None),
    db: Session = Depends(get_db),
):
    if months not in (3, 6, 12):
        months = 6
    today = date_type.today()

    use_month_mode = year is not None and month is not None and 1 <= month <= 12

    if use_month_mode:
        mode = "month"
        range_start, month_end = _month_bounds(year, month)
        # Same cutoff rule as _range_for_period("mtd", ...): don't count/
        # show days that haven't happened yet for the current month; a
        # past month is shown in full, a future month ends up all-zero.
        if year == today.year and month == today.month:
            range_end = today
        else:
            range_end = month_end
    else:
        mode = "rolling"
        year = None
        month = None
        start_y, start_m = _shift_month(today.year, today.month, -(months - 1))
        range_start, _ = _month_bounds(start_y, start_m)
        # Uncapped at today, matching the original trend's current-month
        # bucket (m_start <= date <= m_end) -- unlike month mode's day-level
        # cutoff below, this rolling window was never "as of today" scoped.
        _, range_end = _month_bounds(today.year, today.month)

    fire_quotations = db.query(models.FirePropertyQuotation).filter(
        models.FirePropertyQuotation.quotation_date >= range_start,
        models.FirePropertyQuotation.quotation_date <= range_end,
    ).all()
    motor_quotations = db.query(models.MotorQuotation).filter(
        models.MotorQuotation.quotation_date >= range_start,
        models.MotorQuotation.quotation_date <= range_end,
    ).all()

    fire_converted = sum(1 for q in fire_quotations if q.policy is not None)
    motor_converted = sum(1 for q in motor_quotations if q.policy is not None)

    total_quotations = len(fire_quotations) + len(motor_quotations)
    converted_accounts = fire_converted + motor_converted
    conversion_rate = (converted_accounts / total_quotations * 100) if total_quotations else 0.0

    fire_pie = [
        {"name": "Not Yet Converted", "value": len(fire_quotations) - fire_converted},
        {"name": "Converted Account", "value": fire_converted},
    ]
    motor_pie = [
        {"name": "Not Yet Converted", "value": len(motor_quotations) - motor_converted},
        {"name": "Converted Account", "value": motor_converted},
    ]

    trend = []
    if use_month_mode:
        # Day-level granularity within the one selected month — same
        # per-day bucketing/labeling convention as /stats/policy-distribution
        # MTD's bar_chart (label = plain day number).
        buckets = {d: {"fire": 0, "motor": 0, "fire_conv": 0, "motor_conv": 0} for d in range(1, range_end.day + 1)}
        for q in fire_quotations:
            buckets[q.quotation_date.day]["fire"] += 1
            if q.policy is not None:
                buckets[q.quotation_date.day]["fire_conv"] += 1
        for q in motor_quotations:
            buckets[q.quotation_date.day]["motor"] += 1
            if q.policy is not None:
                buckets[q.quotation_date.day]["motor_conv"] += 1
        for d in sorted(buckets):
            b = buckets[d]
            trend.append({
                "label": str(d),
                "quotation_count": b["fire"] + b["motor"],
                "converted_count": b["fire_conv"] + b["motor_conv"],
            })
    else:
        # Rolling window ending at the current month, oldest first — same
        # non-calendar-year-aligned philosophy as /overview's monthly_line,
        # just parameterized by `months` instead of a fixed 6.
        for delta in range(-(months - 1), 1):
            y, m = _shift_month(today.year, today.month, delta)
            m_start, m_end = _month_bounds(y, m)
            fire_in_month = [q for q in fire_quotations if q.quotation_date and m_start <= q.quotation_date <= m_end]
            motor_in_month = [q for q in motor_quotations if q.quotation_date and m_start <= q.quotation_date <= m_end]
            quotation_count = len(fire_in_month) + len(motor_in_month)
            converted_count = (
                sum(1 for q in fire_in_month if q.policy is not None)
                + sum(1 for q in motor_in_month if q.policy is not None)
            )
            trend.append({"label": MONTH_ABBR[m - 1], "quotation_count": quotation_count, "converted_count": converted_count})

    return {
        "date": today,
        "total_quotations": total_quotations,
        "converted_accounts": converted_accounts,
        "conversion_rate": conversion_rate,
        "fire_pie": fire_pie,
        "motor_pie": motor_pie,
        "mode": mode,
        "range_start": range_start,
        "range_end": range_end,
        "months": None if use_month_mode else months,
        "year": year,
        "month": month,
        "trend": trend,
    }


# ------------------------------------------------------------
# CLAIMS MODULE PAGE (KPI cards + investigation pie + monthly trend -- the
# page's claims TABLE reuses the per-claim REST endpoints, joined in
# Frontend/src/lib/claims.js)
# ------------------------------------------------------------

# Final statuses that mean the claim is finished; everything else is still open.
FINISHED_FINAL_STATUSES = {"Closed Claim", "Denied Claim", "CNC Only", "Not Push Through"}
OPEN_FINAL_STATUSES = set(schemas.CLAIM_FINAL_STATUS_OPTIONS) - FINISHED_FINAL_STATUSES
assert FINISHED_FINAL_STATUSES <= set(schemas.CLAIM_FINAL_STATUS_OPTIONS)

CNC_CLAIM_TYPE = "CNC Issuance"
FRAUD_LABELS = {"Suspected Fraud", "Confirmed Fraud"}


@router.get("/claims", response_model=schemas.ClaimsStats)
def get_claims_stats(
    # Same hand-validated 3/6/12 rolling window as /quotation-proposal.
    months: int = Query(6),
    db: Session = Depends(get_db),
):
    if months not in (3, 6, 12):
        months = 6
    today = date_type.today()
    start_year, start_month = _shift_month(today.year, today.month, -(months - 1))
    range_start, _ = _month_bounds(start_year, start_month)
    _, range_end = _month_bounds(today.year, today.month)

    def filed_in_range(model):
        return db.query(model).filter(
            model.date_reported >= range_start,
            model.date_reported <= range_end,
        ).all()

    motor = filed_in_range(models.MotorClaim)
    fire = filed_in_range(models.FirePropertyClaim)
    claims = motor + fire

    # Investigation result: CNC Issuance rows are never investigated for fraud,
    # so they're left out of the pie, the rate and "not yet investigated".
    investigable = [c for c in claims if c.claim_type != CNC_CLAIM_TYPE]
    result_counts = {label: 0 for label in schemas.CLAIM_INVESTIGATION_RESULT_OPTIONS}
    not_yet_investigated = 0
    for c in investigable:
        if c.claim_investigation_result in result_counts:
            result_counts[c.claim_investigation_result] += 1
        else:
            not_yet_investigated += 1
    investigated = sum(result_counts.values())
    fraud_count = result_counts["Suspected Fraud"] + result_counts["Confirmed Fraud"]

    trend = []
    for delta in range(-(months - 1), 1):
        y, m = _shift_month(today.year, today.month, delta)
        in_month = lambda c: c.date_reported.year == y and c.date_reported.month == m  # noqa: E731
        trend.append({
            "label": MONTH_ABBR[m - 1],
            "year": y,
            "month": m,
            "motor_count": sum(1 for c in motor if in_month(c)),
            "fire_count": sum(1 for c in fire if in_month(c)),
            "fraud_labelled_count": sum(
                1 for c in investigable if in_month(c) and c.claim_investigation_result in FRAUD_LABELS
            ),
        })

    return {
        "date": today,
        "months": months,
        "range_start": range_start,
        "range_end": range_end,
        "period_label": f"Past {months} Months",
        "total_claims": len(claims),
        "motor_claims": len(motor),
        "fire_claims": len(fire),
        "open_claims": sum(1 for c in claims if c.final_status in OPEN_FINAL_STATUSES),
        "closed_claims": sum(1 for c in claims if c.final_status == "Closed Claim"),
        "total_net_liability": sum((c.net_liability or 0) for c in claims),
        "legitimate": result_counts["Legitimate"],
        "suspected_fraud": result_counts["Suspected Fraud"],
        "confirmed_fraud": result_counts["Confirmed Fraud"],
        "not_yet_investigated": not_yet_investigated,
        "cnc_excluded": len(claims) - len(investigable),
        "fraud_rate": (fraud_count / investigated * 100) if investigated else None,
        "investigation_pie": [
            {"name": "Legitimate", "value": result_counts["Legitimate"]},
            {"name": "Suspected Fraud", "value": result_counts["Suspected Fraud"]},
            {"name": "Confirmed Fraud", "value": result_counts["Confirmed Fraud"]},
            {"name": "Not Yet Investigated", "value": not_yet_investigated},
        ],
        "trend": trend,
    }
