from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


# ── Environment ───────────────────────────────────────────────────────────────

class EnvironmentCreate(BaseModel):
    name: str
    display_order: int = 0


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    display_order: int
    created_at: datetime
    updated_at: datetime


# ── TestCase ─────────────────────────────────────────────────────────────────

class TestCaseCreate(BaseModel):
    name: str
    category_id: int
    display_order: int = 0


class TestCaseUpdate(BaseModel):
    name: Optional[str] = None
    display_order: Optional[int] = None


class TestCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category_id: int
    display_order: int
    created_at: datetime
    updated_at: datetime


# ── Category ─────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    slug: str
    name: str
    is_critical: bool = False
    display_order: int = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    is_critical: Optional[bool] = None
    display_order: Optional[int] = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    is_critical: bool
    display_order: int
    created_at: datetime
    updated_at: datetime


class CategoryWithTests(BaseModel):
    """Shape that matches the frontend CATS array entries."""
    model_config = ConfigDict(from_attributes=True)
    id: str          # slug used as id in frontend
    name: str
    critical: bool
    tests: list[str]  # just test names, matching frontend shape


# ── Cluster ──────────────────────────────────────────────────────────────────

class ClusterCreate(BaseModel):
    name: str
    location_id: int


class ClusterUpdate(BaseModel):
    name: Optional[str] = None
    location_id: Optional[int] = None


class ClusterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    location_id: int
    created_at: datetime
    updated_at: datetime


# ── Location ─────────────────────────────────────────────────────────────────

class LocationCreate(BaseModel):
    code: str
    label: str
    zone: str


class LocationUpdate(BaseModel):
    label: Optional[str] = None
    zone: Optional[str] = None


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    label: str
    zone: str
    created_at: datetime
    updated_at: datetime


class LocationWithClusters(BaseModel):
    """Full location with nested cluster names."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    label: str
    zone: str
    clusters: list[str]   # cluster names only


class LocationMapEntry(BaseModel):
    """Value shape inside the LOCS dict the frontend expects."""
    label: str
    clusters: list[str]
