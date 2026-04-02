from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.run import Run
from app.schemas.run import RunCreate, RunUpdate


def create_run(db: Session, payload: RunCreate) -> Run:
    run = Run(**payload.model_dump())
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_run(db: Session, run_id: str) -> Run:
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def get_runs(db: Session, skip: int = 0, limit: int = 100) -> tuple[int, list[Run]]:
    q = db.query(Run).order_by(Run.started_at.desc())
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return total, items


def update_run(db: Session, run_id: str, payload: RunUpdate) -> Run:
    run = get_run(db, run_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(run, k, v)
    db.commit()
    db.refresh(run)
    return run
