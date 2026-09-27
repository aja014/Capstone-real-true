"""Read-only access to the trained models and their predictions (Models Phase 2).
There is deliberately no "train" endpoint — training runs automatically (app/ml/jobs.py)."""
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.ml import jobs, training
from app.ml.report import TITLES
from app.security import get_current_user

router = APIRouter(
    prefix="/ml",
    tags=["Models"],
    dependencies=[Depends(get_current_user)],
)

LINE_OF_TARGET = {"motor_quotation": "Motor Car", "fire_quotation": "Fire & Property",
                  "motor_claim": "Motor Car", "fire_claim": "Fire & Property"}
QUOTATION_TYPES = {"Motor Car": "motor_quotation", "Fire & Property": "fire_quotation"}
CLAIM_TYPES = {"Motor Car": "motor_claim", "Fire & Property": "fire_claim"}


def _first_line(text):
    return text.strip().splitlines()[0] if text else None


def _attempts(db, name):
    return (db.query(models.MLModel).filter(models.MLModel.model_name == name)
            .order_by(models.MLModel.version.desc()).all())


def _summary(name, attempts):
    active = next((a for a in attempts if a.status == "active"), None)
    latest = attempts[0] if attempts else None
    out = {"model_name": name, "title": TITLES[name], "available": active is not None,
           "last_failure": None}
    if latest is not None and latest.status == "failed":
        out["last_failure"] = {"version": latest.version, "trained_at": latest.trained_at,
                               "error": _first_line(latest.error)}
    if active is None:
        return out
    m = active.metrics or {}
    test = m.get("test", {})
    cv = m.get("cross_validation", {})
    out.update(
        version=active.version, trained_at=active.trained_at, data_as_of=active.data_as_of,
        train_rows=active.train_rows, test_rows=active.test_rows, positive_rows=active.positive_rows,
        thresholds=active.thresholds,
        test={k: test.get(k) for k in ("accuracy", "precision", "recall", "f1", "roc_auc")},
        cross_validation={k: {"mean": v["mean"], "sd": v["sd"]} for k, v in cv.items()},
        report_file=Path(active.report_path).name if active.report_path else None,
    )
    return out


@router.get("/models", response_model=schemas.MLModelsOverview)
def list_models(db: Session = Depends(get_db)):
    """The active version of each model with its headline test / cross-validation scores,
    plus the state of the automatic refresh."""
    return {"models": [_summary(n, _attempts(db, n)) for n in training.MODEL_NAMES],
            "refresh": dict(jobs.status)}


@router.get("/models/{model_name}", response_model=schemas.MLModelDetail)
def get_model(model_name: str, db: Session = Depends(get_db)):
    """Full metrics of the active version (confusion matrix, CV per fold, top clues, ...)
    plus every training attempt of this model."""
    if model_name not in training.MODEL_NAMES:
        raise HTTPException(status_code=404, detail="Model not found")
    attempts = _attempts(db, model_name)
    active = next((a for a in attempts if a.status == "active"), None)
    return {
        **_summary(model_name, attempts),
        "metrics": active.metrics if active else None,
        "history": [{"version": a.version, "status": a.status, "trained_at": a.trained_at,
                     "data_as_of": a.data_as_of, "error": _first_line(a.error)} for a in attempts],
    }


def _predictions(db, target_types):
    return (db.query(models.MLPrediction, models.MLModel.version)
            .join(models.MLModel, models.MLModel.id == models.MLPrediction.model_id)
            .filter(models.MLPrediction.target_type.in_(target_types))
            .order_by(models.MLPrediction.target_type, models.MLPrediction.target_id).all())


@router.get("/predictions/quotations", response_model=list[schemas.QuotationPrediction])
def quotation_predictions(line: Optional[Literal["Motor Car", "Fire & Property"]] = Query(None),
                          db: Session = Depends(get_db)):
    """Claim Possibility + Risk Assessment for open quotations and quotations whose policy is
    in force. Quotations not listed have no prediction (their policy has ended)."""
    types = [QUOTATION_TYPES[line]] if line else list(QUOTATION_TYPES.values())
    return [{"line": LINE_OF_TARGET[p.target_type], "quotation_id": p.target_id,
             "claim_probability": float(p.probability), "risk_level": p.label,
             "model_version": version, "predicted_at": p.predicted_at}
            for p, version in _predictions(db, types)]


@router.get("/predictions/claims", response_model=list[schemas.ClaimPrediction])
def claim_predictions(line: Optional[Literal["Motor Car", "Fire & Property"]] = Query(None),
                      db: Session = Depends(get_db)):
    """Fraud Warning for Paid Claims not yet investigated. Investigated claims and CNC
    Issuance rows are never listed."""
    types = [CLAIM_TYPES[line]] if line else list(CLAIM_TYPES.values())
    return [{"line": LINE_OF_TARGET[p.target_type], "claim_id": p.target_id,
             "fraud_probability": float(p.probability), "label": p.label,
             "model_version": version, "predicted_at": p.predicted_at}
            for p, version in _predictions(db, types)]
