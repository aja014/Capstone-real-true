"""
Cross-cutting bulk-import logic shared by the Policy importers (Fire/Property and
Motor). Deliberately NOT imported by import_fire_property.py / import_motor.py
themselves — import_policyholders.py already imports both of those, so importing
either of them here would create a circular import. Per-file helpers like
clean_cell_value/normalize_header/full_name/normalize_phone stay duplicated in each
importer file, consistent with the existing convention (already duplicated 3x before
this file existed).
"""
from datetime import date as date_type

from app import models

CONFIDENT_THRESHOLD = 75
AMBIGUITY_MARGIN = 15


def require_name(first_name, last_name, context: str) -> None:
    """
    A policyholder needs at least SOME name -- either part of a person's name, or a
    business name in last_name (see PolicyholderCreate.first_name's Optional comment
    in schemas.py). Without this check, a mis-mapped header (e.g. blank insured_name)
    could silently create an unusable Policyholder with both fields None -- exactly
    what happened before this existed: 4 real rows crashed GET /policyholders because
    the read schema assumed last_name was never blank.
    """
    if not (first_name or "").strip() and not (last_name or "").strip():
        raise ValueError(f"{context}: cannot create a policyholder with a completely blank name")


def split_insured_name_address(value):
    """
    Policy source rows carry name+address combined in one field (insured_name_address
    on both FirePropertyPolicy and MotorPolicy — no separate name column exists).
    Splits on the first comma ("NAME, ADDRESS"); no comma -> whole string is the name,
    address is "". Policyholder matching for the two Policy importers deliberately
    reuses each line's OWN existing match_score (Fire/Property's or Motor's) against
    just the extracted name, rather than a separate address-aware formula — a
    policyholder that already auto-matches via that line's Survey/Quotation importer
    should also auto-match via its Policy importer, not require extra corroboration
    just because it came in through a different importer. The extracted address is
    still used to populate present_address when a brand-new policyholder is created.
    """
    if not value:
        return "", ""
    parts = str(value).split(",", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return str(value).strip(), ""


def _date_score(candidate_date, existing_date) -> float:
    if not candidate_date or not existing_date:
        return 0
    delta = abs((candidate_date - existing_date).days)
    if delta <= 7:
        return 100
    if delta <= 30:
        return 85
    if delta <= 90:
        return 65
    if delta <= 180:
        return 40
    return 15  # never fully 0 -- a quotation can legitimately predate a policy by months


def _amount_score(candidate_amount, existing_amount) -> float:
    if candidate_amount is None or existing_amount is None:
        return 0
    try:
        candidate_amount = float(candidate_amount)
        existing_amount = float(existing_amount)
    except (TypeError, ValueError):
        return 0
    if candidate_amount == 0 and existing_amount == 0:
        return 100
    denom = max(abs(candidate_amount), abs(existing_amount), 1)
    pct_diff = abs(candidate_amount - existing_amount) / denom
    return max(0.0, 100 - pct_diff * 200)


def _unattached_quotations(db, policyholder_id, line_type, quotation_model, policy_model):
    """
    A policy's required quotation_id FK means bulk-importing a Policy row has to guess
    which of a policyholder's quotations it belongs to -- there's no shared ID in the
    source data. Only quotations that don't already have a policy are candidates.
    """
    return (
        db.query(quotation_model)
        .join(models.InsuranceCase, quotation_model.insurance_case_id == models.InsuranceCase.id)
        .outerjoin(policy_model, policy_model.quotation_id == quotation_model.id)
        .filter(
            models.InsuranceCase.policyholder_id == policyholder_id,
            models.InsuranceCase.line_type == line_type,
            policy_model.id.is_(None),
        )
        .all()
    )


def find_best_unattached_quotation(db, policyholder_id, line_type, quotation_model, policy_model,
                                    amount_getter, date_getter, candidate_amount, candidate_date) -> dict:
    """
    Scores a policyholder's still-open quotations by how close their amount/date are to
    the policy row being imported. Returns {"status": "confident"|"ambiguous"|"none",
    "candidate": <ORM row or None>, "candidates_considered": [...]}.
    """
    quotations = _unattached_quotations(db, policyholder_id, line_type, quotation_model, policy_model)

    scored = []
    for q in quotations:
        amount_score = _amount_score(candidate_amount, amount_getter(q))
        date_score = _date_score(candidate_date, date_getter(q))
        combined = amount_score * 0.7 + date_score * 0.3
        scored.append({"quotation": q, "id": q.id, "amount": amount_getter(q), "date": date_getter(q), "score": combined})

    scored.sort(key=lambda s: s["score"], reverse=True)
    considered = [{"id": s["id"], "amount": s["amount"], "date": s["date"], "score": s["score"]} for s in scored]

    if not scored:
        return {"status": "none", "candidate": None, "candidates_considered": considered}

    top = scored[0]
    runner_up = scored[1] if len(scored) > 1 else None

    if top["score"] >= CONFIDENT_THRESHOLD and (runner_up is None or top["score"] - runner_up["score"] >= AMBIGUITY_MARGIN):
        return {"status": "confident", "candidate": top["quotation"], "candidates_considered": considered}

    return {"status": "ambiguous", "candidate": None, "candidates_considered": considered}


def list_quotation_candidates(db, policyholder_id, line_type, quotation_model, policy_model,
                               amount_getter, date_getter) -> list[dict]:
    """All of a policyholder's still-open quotations for a line -- for the manual quotation-picker UI."""
    quotations = _unattached_quotations(db, policyholder_id, line_type, quotation_model, policy_model)
    quotations.sort(key=lambda q: date_getter(q) or date_type.min, reverse=True)
    return [
        {"id": q.id, "quotation_date": date_getter(q), "amount": amount_getter(q), "case_id": q.insurance_case_id}
        for q in quotations
    ]
