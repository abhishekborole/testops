from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.run import RunCreate, RunUpdate, RunResponse
from app.services import run_service

router = APIRouter(prefix="/runs", tags=["Runs"])


@router.post("/", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate, db: Session = Depends(get_db)):
    return run_service.create_run(db, payload)


@router.get("/", response_model=dict)
def list_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    total, items = run_service.get_runs(db, skip=skip, limit=limit)
    return {"total": total, "items": [RunResponse.model_validate(r) for r in items]}


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, db: Session = Depends(get_db)):
    return run_service.get_run(db, run_id)


@router.patch("/{run_id}", response_model=RunResponse)
def update_run(run_id: str, payload: RunUpdate, db: Session = Depends(get_db)):
    return run_service.update_run(db, run_id, payload)
