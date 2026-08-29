"""
Folder-based bulk import: given several Excel files at once (of possibly different
document types), figure out which importer each one belongs to by reading its column
headers, then run each through its existing per-file pipeline.

Two-phase flow:
  1. POST /detect  — header-only peek at every file, returns a best-guess type +
     confidence per file. No DB writes. The frontend shows this as an editable/
     confirmable per-file table before anything is actually imported.
  2. POST /upload  — the same files, now paired with a user-confirmed import_type per
     file, dispatched to the corresponding existing upload_* function.
"""
import re

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.routers import import_policyholders, import_fire_property, import_motor

router = APIRouter(
    prefix="/import/batch",
    tags=["Bulk Import — Batch"],
    dependencies=[Depends(get_current_user)],
)

# Score thresholds for header-based detection — same "tune later with real data"
# status as every other matching threshold in this codebase.
DETECT_CONFIDENT_SCORE = 55
AMBIGUITY_MARGIN = 12

IMPORT_TYPE_REGISTRY = [
    {
        "key": models.ImportType.policyholder,
        "label": "Customer / Policyholder Information",
        "column_map": import_policyholders.COLUMN_MAP,
        "upload_fn": import_policyholders.upload_policyholders,
    },
    {
        "key": models.ImportType.fire_property,
        "label": "Fire & Property Survey",
        "column_map": import_fire_property.SURVEY_COLUMN_MAP,
        "upload_fn": import_fire_property.upload_surveys,
    },
    {
        "key": models.ImportType.fire_property_quotation,
        "label": "Fire & Property Quotation",
        "column_map": import_fire_property.FIRE_QUOTATION_COLUMN_MAP,
        "upload_fn": import_fire_property.upload_fire_property_quotations,
    },
    {
        "key": models.ImportType.fire_property_policy,
        "label": "Fire & Property Policy",
        "column_map": import_fire_property.FIRE_POLICY_COLUMN_MAP,
        "upload_fn": import_fire_property.upload_fire_property_policies,
    },
    {
        "key": models.ImportType.motor,
        "label": "Motor Quotation",
        "column_map": import_motor.COLUMN_MAP,
        "upload_fn": import_motor.upload_motor_quotations,
    },
    {
        "key": models.ImportType.motor_policy,
        "label": "Motor Policy",
        "column_map": import_motor.MOTOR_POLICY_COLUMN_MAP,
        "upload_fn": import_motor.upload_motor_policies,
    },
]


def _normalize_header(header) -> str:
    return re.sub(r"[^a-z0-9]", "", str(header).strip().lower())


def score_against_map(file_headers_norm: set, column_map: dict) -> tuple[float, list[str]]:
    """
    Precision of the file's headers against one importer's known columns -- i.e. "of
    the columns THIS file actually has, how many belong to this type". Deliberately
    NOT recall-weighted (an F1-style score against the full column map): a real export
    that only populates a handful of optional fields would otherwise score low against
    a map with many optional columns even when every one of its headers is an exact,
    unambiguous match. A lone coincidentally-shared column (e.g. "Date", used by
    several types) is still weak evidence on its own, so it's dampened rather than
    trusted at full strength.
    """
    map_keys = set(column_map.keys())
    if not map_keys or not file_headers_norm:
        return 0.0, []

    matched = file_headers_norm & map_keys
    if not matched:
        return 0.0, []

    score = (len(matched) / len(file_headers_norm)) * 100
    if len(matched) == 1 and len(file_headers_norm) > 1:
        score *= 0.6

    matched_fields = sorted({column_map[k] for k in matched})
    return score, matched_fields


def detect_headers(headers: list) -> list[dict]:
    file_headers_norm = {_normalize_header(h) for h in headers}
    candidates = []
    for entry in IMPORT_TYPE_REGISTRY:
        score, matched_fields = score_against_map(file_headers_norm, entry["column_map"])
        candidates.append({
            "import_type": entry["key"],
            "label": entry["label"],
            "score": round(score, 1),
            "matched_columns": matched_fields,
        })
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def _read_header_row(file: UploadFile) -> list:
    name = file.filename.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(file.file, nrows=0)
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file.file, nrows=0)
    else:
        raise ValueError("Only .xlsx, .xls, or .csv files are supported")
    return list(df.columns)


@router.post("/detect", response_model=schemas.BatchDetectResult)
def detect_batch(files: list[UploadFile] = File(...)):
    results = []

    for f in files:
        try:
            headers = _read_header_row(f)
        except Exception as e:
            results.append(schemas.DetectedFile(
                filename=f.filename, candidates=[], best_guess=None,
                confidence="none", ambiguous=False, error=f"Could not read file: {e}",
            ))
            continue

        candidates = detect_headers(headers)
        top = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        gap = top["score"] - (runner_up["score"] if runner_up else -1)

        if top["score"] <= 0:
            confidence, best_guess, ambiguous = "none", None, False
        elif top["score"] >= DETECT_CONFIDENT_SCORE and gap >= AMBIGUITY_MARGIN:
            confidence, best_guess, ambiguous = "high", top["import_type"], False
        elif top["score"] >= DETECT_CONFIDENT_SCORE:
            # Strong match, but a close runner-up (e.g. Fire vs Motor Policy files
            # share nearly all their columns) -- genuinely ambiguous, don't guess.
            confidence, best_guess, ambiguous = "low", None, True
        else:
            confidence, best_guess, ambiguous = "low", None, False

        results.append(schemas.DetectedFile(
            filename=f.filename,
            candidates=[schemas.ImportTypeCandidate(**c) for c in candidates],
            best_guess=best_guess,
            confidence=confidence,
            ambiguous=ambiguous,
        ))

    return schemas.BatchDetectResult(files=results)


# Files must be processed in dependency order regardless of what order the
# browser handed them in (its folder picker lists files alphabetically, which
# has no relation to what each document type depends on). A Policy needs its
# Quotation to already exist; a Quotation is best matched against a case a
# Survey already created. Without this, e.g. "fire_property_policy.xlsx"
# sorts before "fire_property_quotation.xlsx" alphabetically and the policy
# row finds no quotation to attach to yet, even though one is in the same
# folder -- found via real end-to-end testing, not a hypothetical.
PROCESSING_PRIORITY = {
    models.ImportType.policyholder.value: 0,
    models.ImportType.fire_property.value: 1,
    models.ImportType.motor.value: 1,
    models.ImportType.fire_property_quotation.value: 2,
    models.ImportType.fire_property_policy.value: 3,
    models.ImportType.motor_policy.value: 3,
}


@router.post("/upload", response_model=schemas.BatchImportSummary)
def upload_batch(
    files: list[UploadFile] = File(...),
    import_types: list[str] = Form(...),
    db: Session = Depends(get_db),
):
    """
    `files` and `import_types` must be appended in matching order by the client --
    import_types[i] is the confirmed type for files[i]. Actual processing order
    follows PROCESSING_PRIORITY, not this input order -- see comment above.
    """
    if len(files) != len(import_types):
        raise HTTPException(
            status_code=400,
            detail="files and import_types must be the same length and in matching order",
        )

    fn_by_key = {entry["key"].value: entry["upload_fn"] for entry in IMPORT_TYPE_REGISTRY}
    for t in import_types:
        if t not in fn_by_key:
            raise HTTPException(status_code=400, detail=f"Unknown import type: {t}")

    # Sort by dependency priority (stable -- ties keep their original relative
    # order), process in that order, then hand results back in the ORIGINAL
    # order so the response lines up with what the user confirmed in the UI.
    indexed = list(enumerate(zip(files, import_types)))
    indexed.sort(key=lambda item: PROCESSING_PRIORITY.get(item[1][1], 99))

    results_by_index = {}
    for original_index, (f, type_str) in indexed:
        upload_fn = fn_by_key[type_str]
        try:
            # Direct function call, not an HTTP request -- file/db are passed as real
            # arguments, which simply overrides each function's Depends(...)/File(...)
            # defaults rather than going through FastAPI's request-handling machinery.
            summary = upload_fn(file=f, db=db)
            results_by_index[original_index] = schemas.BatchFileResult(filename=f.filename, import_type=type_str, summary=summary)
        except HTTPException as e:
            results_by_index[original_index] = schemas.BatchFileResult(filename=f.filename, import_type=type_str, error=str(e.detail))
        except Exception as e:
            results_by_index[original_index] = schemas.BatchFileResult(filename=f.filename, import_type=type_str, error=str(e))

    results = [results_by_index[i] for i in range(len(files))]
    return schemas.BatchImportSummary(files=results)
