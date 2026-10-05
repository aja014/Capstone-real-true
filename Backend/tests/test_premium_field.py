"""Fire policy "Premium" (2026-10-05, branch premium-field).

The old field unit_cost_premium wrongly merged the form's separate Unit Cost and Premium
columns. It is now `premium` = the policy's Total Premium in pesos, before taxes (Maagap's real
fire policy: Total Amount Due = Total Premium x 1.27). The old header "Unit Cost Premium" held a
rate per P1,000, so it must not be read into `premium`. No database access: pure parsing,
detection and schema checks."""
import pandas as pd

from app import schemas
from app.routers import import_batch
from app.routers.import_fire_property import row_to_fire_policy_fields

V3_FIRE_POLICY_HEADERS = [
    "Issue Date", "Insured Name & Address", "Line of Insurance", "Policy No.", "Renewing Policy No.",
    "Period From", "Period To", "Total Amount Due", "Sum Insured", "Agency Code", "TIN", "Premium Invoice No.",
    "Official Receipt No.", "Replacing Cover Note No.", "Property Insured", "Construction", "Occupancy",
    "Coverage Description", "Premium",
]


def test_premium_read_as_money_and_old_header_not_mapped():
    row = pd.Series({
        "Policy No.": "ZZTEST-FP-PREMIUM",
        "Total Amount Due": "₱16,383.00",
        "Premium": "₱12,900.00",
        "Unit Cost Premium": "3.12",
    })
    fields = row_to_fire_policy_fields(row)
    assert fields["premium"] == "12900.00"
    assert fields["total_amount_due"] == "16383.00"
    assert "unit_cost_premium" not in fields
    # The rate never lands in premium, whichever column comes first.
    assert row_to_fire_policy_fields(pd.Series({"Unit Cost Premium": "3.12"})) == {}


def test_auto_detect_still_picks_fire_policy():
    for headers in (V3_FIRE_POLICY_HEADERS,
                    [h if h != "Premium" else "Unit Cost Premium" for h in V3_FIRE_POLICY_HEADERS]):
        candidates = import_batch.detect_headers(headers)
        top, runner_up = candidates[0], candidates[1]
        assert top["import_type"] == "fire_property_policy"
        assert top["score"] >= import_batch.DETECT_CONFIDENT_SCORE
        assert top["score"] - runner_up["score"] >= import_batch.AMBIGUITY_MARGIN


def test_policy_schema_has_premium_not_unit_cost_premium():
    out_fields = schemas.FirePropertyPolicyOut.model_fields
    assert "premium" in out_fields
    assert "unit_cost_premium" not in out_fields
