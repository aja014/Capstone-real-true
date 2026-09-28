"""Policy Forecast (Proposal page card) — plain statistics, NOT one of the ML models.

Next month's new policies, per line
    = quotations sent per month (average of the past 12 months) × conversion rate.
Conversion rate = quotations that became a policy within the waiting period W ÷ all quotations
old enough to be decided (at least W days old), past 12 months. W = the 95th percentile of the
days from quotation to policy, rounded up (7 days in the current data).

Open quotations (younger than W, no policy yet) are shown separately as "policies expected
within the next W days": each one counts with the chance that past quotations of the same age,
still unconverted at that age, became a policy. They are not added to next month's number
(most of them are decided before the month starts).

Everything is computed from (quotation_date, issue_date or None) pairs and an as-of date, using
only facts dated on or before that day, so the backtest runs the same code as the live card.
Report: `python -m app.services.policy_forecast` from Backend/ writes
model_reports/<as of>_policy_forecast_backtest.md."""
import calendar
import math
from datetime import date
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from app import models

HISTORY_DAYS = 365  # "past 12 months", for both the quotation volume and the conversion rate
WAIT_PERCENTILE = 95
BACKTEST_MONTHS = 12

LINES = (
    ("Motor Car", models.MotorQuotation, models.MotorPolicy),
    ("Fire & Property", models.FirePropertyQuotation, models.FirePropertyPolicy),
)
MONTH_NAMES = [calendar.month_name[m] for m in range(1, 13)]
REPORT_DIR = Path(__file__).resolve().parents[3] / "model_reports"


def load_rows(db: Session) -> dict[str, list[tuple[date, date | None]]]:
    """line -> [(quotation_date, issue_date or None)]; quotations without a date are left out.
    A policy with no issue date counts as issued on the quotation date."""
    rows = {}
    for line, quotation_model, policy_model in LINES:
        result = (
            db.query(quotation_model.quotation_date, policy_model.issue_date, policy_model.id)
            .outerjoin(policy_model, policy_model.quotation_id == quotation_model.id)
            .filter(quotation_model.quotation_date.isnot(None))
            .order_by(quotation_model.id)
            .all()
        )
        rows[line] = [(q, (i or q) if policy_id is not None else None) for q, i, policy_id in result]
    return rows


def known_rows(rows, as_of):
    """Only what was on file at the end of `as_of`: later quotations and policies removed."""
    return [(q, i if i is not None and i <= as_of else None) for q, i in rows if q <= as_of]


def wait_days(rows, as_of) -> int:
    lags = [(i - q).days for q, i in known_rows(rows, as_of) if i is not None]
    return math.ceil(np.percentile(lags, WAIT_PERCENTILE)) if lags else 0


def next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def open_probability(rate, lag_share, wait, age) -> float:
    """P(becomes a policy | still unconverted at `age` days), from past quotations:
    the share that converted after `age` ÷ the share still unconverted at `age`."""
    still_open = 1 - rate * sum(lag_share[lag] for lag in range(age + 1))
    if still_open <= 0:
        return 0.0
    return rate * sum(lag_share[lag] for lag in range(age + 1, wait + 1)) / still_open


def line_forecast(rows, as_of) -> dict:
    known = known_rows(rows, as_of)
    wait = wait_days(rows, as_of)

    def age(q):
        return (as_of - q).days

    decided = [(q, i) for q, i in known if wait <= age(q) < wait + HISTORY_DAYS]
    lags = [(i - q).days for q, i in decided if i is not None and (i - q).days <= wait]
    rate = len(lags) / len(decided) if decided else None
    lag_share = {lag: lags.count(lag) / len(lags) for lag in range(wait + 1)} if lags else None

    volume = sum(1 for q, _ in known if age(q) < HISTORY_DAYS)
    open_ages = [age(q) for q, i in known if i is None and age(q) < wait]
    if rate is None:
        expected_from_open = None
    elif lag_share is None:
        expected_from_open = 0.0
    else:
        expected_from_open = sum(open_probability(rate, lag_share, wait, a) for a in open_ages)
    return {
        "wait_days": wait,
        "decided_quotations": len(decided),
        "converted_quotations": len(lags),
        "conversion_rate": rate,
        "quotations_past_12_months": volume,
        "avg_quotations_per_month": volume / 12,
        "expected_policies": volume / 12 * rate if rate is not None else None,
        "open_quotations": len(open_ages),
        "expected_from_open": expected_from_open,
    }


def issued_in_month(rows, year, month) -> int:
    first, last = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    return sum(1 for _, i in rows if i is not None and first <= i <= last)


def open_converted(rows, as_of, wait) -> int:
    """Actual policies from the quotations that were open at the end of `as_of`."""
    return sum(1 for q, i in rows
               if q <= as_of and (as_of - q).days < wait and i is not None and i > as_of)


def error_pct(pairs) -> float | None:
    """Average monthly error: mean of |forecast − actual| ÷ actual (months with actual 0 left out)."""
    errors = [abs(f - a) / a for f, a in pairs if f is not None and a]
    return sum(errors) / len(errors) * 100 if errors else None


def total_error_pct(pairs) -> float | None:
    """Signed error of the summed forecasts vs the summed actuals."""
    pairs = [(f, a) for f, a in pairs if f is not None]
    actual = sum(a for _, a in pairs)
    return (sum(f for f, _ in pairs) - actual) / actual * 100 if actual else None


def backtest(rows_by_line, as_of) -> tuple[list[dict], dict]:
    """For each of the last BACKTEST_MONTHS complete months: on the 1st of the month before it,
    forecast it with only that day's data, then compare with the policies actually issued."""
    targets = []
    y, m = as_of.year, as_of.month
    for _ in range(BACKTEST_MONTHS):
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        targets.append((y, m))
    targets.reverse()

    table = []
    pairs = {line: [] for line in rows_by_line}
    open_pairs = {line: [] for line in rows_by_line}
    for ty, tm in targets:
        made_on = date(ty - 1, 12, 1) if tm == 1 else date(ty, tm - 1, 1)
        row = {"as_of": made_on, "target_year": ty, "target_month": tm,
               "target_label": f"{MONTH_NAMES[tm - 1]} {ty}", "lines": []}
        for line, rows in rows_by_line.items():
            fc = line_forecast(rows, made_on)
            actual = issued_in_month(rows, ty, tm)
            open_actual = open_converted(rows, made_on, fc["wait_days"])
            pairs[line].append((fc["expected_policies"], actual))
            open_pairs[line].append((fc["expected_from_open"], open_actual))
            row["lines"].append({
                "line": line, "forecast": fc["expected_policies"], "actual": actual,
                "open_quotations": fc["open_quotations"], "open_forecast": fc["expected_from_open"],
                "open_actual": open_actual,
            })
        forecasts = [ln["forecast"] for ln in row["lines"]]
        row["total_forecast"] = None if None in forecasts else sum(forecasts)
        row["total_actual"] = sum(ln["actual"] for ln in row["lines"])
        table.append(row)

    errors = {line: {"backtest_error_pct": error_pct(pairs[line]),
                     "backtest_total_error_pct": total_error_pct(pairs[line]),
                     "open_backtest_error_pct": total_error_pct(open_pairs[line])}
              for line in rows_by_line}
    total_pairs = [(r["total_forecast"], r["total_actual"]) for r in table]
    errors["total"] = {"backtest_error_pct": error_pct(total_pairs),
                       "backtest_total_error_pct": total_error_pct(total_pairs)}
    return table, errors


def build_forecast(db: Session, as_of: date) -> dict:
    rows_by_line = load_rows(db)
    table, errors = backtest(rows_by_line, as_of)
    lines = [{"line": line, **line_forecast(rows, as_of), **errors[line]}
             for line, rows in rows_by_line.items()]

    def total(key):
        values = [ln[key] for ln in lines]
        return None if None in values else sum(values)

    ty, tm = next_month(as_of.year, as_of.month)
    return {
        "as_of": as_of,
        "target_year": ty,
        "target_month": tm,
        "target_label": f"{MONTH_NAMES[tm - 1]} {ty}",
        "history_months": 12,
        "expected_policies": total("expected_policies"),
        "avg_quotations_per_month": total("avg_quotations_per_month"),
        "open_quotations": total("open_quotations"),
        "expected_from_open": total("expected_from_open"),
        "backtest_error_pct": errors["total"]["backtest_error_pct"],
        "backtest_total_error_pct": errors["total"]["backtest_total_error_pct"],
        "lines": lines,
        "backtest": table,
    }


def _fmt(value, digits=1, suffix=""):
    return "—" if value is None else f"{value:.{digits}f}{suffix}"


def write_report(fc: dict) -> Path:
    motor, fire = fc["lines"]
    out = [
        f"# Policy Forecast — backtest (as of {fc['as_of']})",
        "",
        "Plain statistics, not one of the ML models. Next month's new policies per line = average "
        "quotations per month (past 12 months) × conversion rate (past 12 months of quotations old "
        "enough to be decided, i.e. at least W days old).",
        "",
        "## Live forecast",
        "",
        f"**{fc['target_label']}: ≈ {_fmt(fc['expected_policies'])} new policies.** Open quotations "
        f"now: {fc['open_quotations']} → ≈ {_fmt(fc['expected_from_open'])} policies within the "
        "waiting period (shown separately, not added).",
        "",
        "| Line | Waiting period W | Converted / decided | Conversion rate | Quotations, past 12 months "
        "| Per month | Forecast | Open | Expected from open |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for ln in fc["lines"]:
        rate = None if ln["conversion_rate"] is None else ln["conversion_rate"] * 100
        out.append(
            f"| {ln['line']} | {ln['wait_days']} days | {ln['converted_quotations']} / "
            f"{ln['decided_quotations']} | {_fmt(rate, 1, '%')} | {ln['quotations_past_12_months']} | "
            f"{_fmt(ln['avg_quotations_per_month'])} | {_fmt(ln['expected_policies'])} | "
            f"{ln['open_quotations']} | {_fmt(ln['expected_from_open'])} |")
    out += [
        "",
        "## Backtest",
        "",
        "On the 1st of each month, the forecast for the NEXT month was computed with only the data on "
        "file that day, then compared with the policies actually issued in that month.",
        "",
        "| Forecast made | Month | Motor forecast | Motor actual | Fire & Property forecast "
        "| Fire & Property actual | Total forecast | Total actual | Difference |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in fc["backtest"]:
        m, f = r["lines"]
        diff = "—" if r["total_forecast"] is None else f"{r['total_forecast'] - r['total_actual']:+.1f}"
        out.append(
            f"| {r['as_of']} | {r['target_label']} | {_fmt(m['forecast'])} | {m['actual']} | "
            f"{_fmt(f['forecast'])} | {f['actual']} | {_fmt(r['total_forecast'])} | "
            f"{r['total_actual']} | {diff} |")
    out += [
        "",
        "| | Average monthly error | 12-month total error |",
        "|---|---|---|",
        f"| Motor Car | {_fmt(motor['backtest_error_pct'], 1, '%')} | "
        f"{_fmt(motor['backtest_total_error_pct'], 1, '%')} |",
        f"| Fire & Property | {_fmt(fire['backtest_error_pct'], 1, '%')} | "
        f"{_fmt(fire['backtest_total_error_pct'], 1, '%')} |",
        f"| Total | {_fmt(fc['backtest_error_pct'], 1, '%')} | {_fmt(fc['backtest_total_error_pct'], 1, '%')} |",
        "",
        "Average monthly error = mean of |forecast − actual| ÷ actual. 12-month total error = "
        "(sum of forecasts − sum of actuals) ÷ sum of actuals.",
        "",
        "### Open quotations (next W days)",
        "",
        "Each open quotation counts with the chance that past quotations of the same age, still "
        "unconverted at that age, became a policy. Compared with the policies those same quotations "
        "actually became:",
        "",
        "| Forecast made | Motor open | Motor expected | Motor actual | Fire & Property open "
        "| Fire & Property expected | Fire & Property actual |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in fc["backtest"]:
        m, f = r["lines"]
        out.append(
            f"| {r['as_of']} | {m['open_quotations']} | {_fmt(m['open_forecast'])} | {m['open_actual']} | "
            f"{f['open_quotations']} | {_fmt(f['open_forecast'])} | {f['open_actual']} |")
    out += [
        "",
        f"12-month total error: Motor {_fmt(motor['open_backtest_error_pct'], 1, '%')}, "
        f"Fire & Property {_fmt(fire['open_backtest_error_pct'], 1, '%')}.",
        "",
        "## Notes",
        "",
        "- The data is synthetic, with steady volume and no seasonality, so a plain average of past "
        "monthly policies is about as accurate. Splitting it into quotation volume × conversion rate "
        "shows the two things Maagap can act on.",
        "- A quotation that becomes a policy more than W days after it was sent counts as not "
        "converted in the rate (none do in the current data).",
    ]
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / f"{fc['as_of']}_policy_forecast_backtest.md"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        print(write_report(build_forecast(session, date.today())))
    finally:
        session.close()
