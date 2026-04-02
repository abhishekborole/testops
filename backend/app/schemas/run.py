from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict


class RunCreate(BaseModel):
    id: str
    status: str = "running"
    env: str
    location: str
    cluster: str
    overall_rate: float = 0.0
    verdict: str = "running"
    categories: list[Any] = []
    started_at: datetime
    completed_at: Optional[datetime] = None


class RunUpdate(BaseModel):
    status: Optional[str] = None
    overall_rate: Optional[float] = None
    verdict: Optional[str] = None
    categories: Optional[list[Any]] = None
    completed_at: Optional[datetime] = None


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    env: str
    location: str
    cluster: str
    overall_rate: float
    verdict: str
    categories: list[Any]
    started_at: datetime
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
