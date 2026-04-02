from typing import Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.ref import (
    LocationCreate, LocationUpdate, LocationResponse, LocationWithClusters,
    ClusterCreate, ClusterUpdate, ClusterResponse,
    CategoryCreate, CategoryUpdate, CategoryResponse, CategoryWithTests,
    TestCaseCreate, TestCaseUpdate, TestCaseResponse,
    LocationMapEntry, EnvironmentCreate, EnvironmentResponse,
)
from app.services import ref_service

router = APIRouter(prefix="/ref", tags=["Reference Data"])


# ── Frontend-shaped endpoints (no auth — read-only reference data) ────────────

@router.get("/locations/map", response_model=dict[str, LocationMapEntry])
def locations_map(db: Session = Depends(get_db)):
    """Returns LOCS-shaped dict identical to frontend constants.js."""
    return ref_service.get_locations_map(db)


@router.get("/categories/flat", response_model=list[CategoryWithTests])
def categories_flat(db: Session = Depends(get_db)):
    """Returns CATS-shaped array identical to frontend constants.js."""
    return ref_service.get_categories_flat(db)


# ── Locations CRUD ────────────────────────────────────────────────────────────

@router.get("/locations", response_model=list[LocationWithClusters])
def list_locations(db: Session = Depends(get_db)):
    locs = ref_service.get_locations(db)
    return [
        LocationWithClusters(
            id=loc.id, code=loc.code, label=loc.label, zone=loc.zone,
            clusters=[c.name for c in loc.clusters],
            created_at=loc.created_at, updated_at=loc.updated_at,
        )
        for loc in locs
    ]


@router.post("/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
def create_location(payload: LocationCreate, db: Session = Depends(get_db)):
    return ref_service.create_location(db, payload)


@router.get("/locations/{location_id}", response_model=LocationWithClusters)
def get_location(location_id: int, db: Session = Depends(get_db)):
    loc = ref_service.get_location(db, location_id)
    return LocationWithClusters(
        id=loc.id, code=loc.code, label=loc.label, zone=loc.zone,
        clusters=[c.name for c in loc.clusters],
        created_at=loc.created_at, updated_at=loc.updated_at,
    )


@router.put("/locations/{location_id}", response_model=LocationResponse)
def update_location(location_id: int, payload: LocationUpdate, db: Session = Depends(get_db)):
    return ref_service.update_location(db, location_id, payload)


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(location_id: int, db: Session = Depends(get_db)):
    ref_service.delete_location(db, location_id)


# ── Clusters CRUD ─────────────────────────────────────────────────────────────

@router.get("/clusters", response_model=list[ClusterResponse])
def list_clusters(location_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    return ref_service.get_clusters(db, location_id)


@router.post("/clusters", response_model=ClusterResponse, status_code=status.HTTP_201_CREATED)
def create_cluster(payload: ClusterCreate, db: Session = Depends(get_db)):
    return ref_service.create_cluster(db, payload)


@router.get("/clusters/{cluster_id}", response_model=ClusterResponse)
def get_cluster(cluster_id: int, db: Session = Depends(get_db)):
    return ref_service.get_cluster(db, cluster_id)


@router.put("/clusters/{cluster_id}", response_model=ClusterResponse)
def update_cluster(cluster_id: int, payload: ClusterUpdate, db: Session = Depends(get_db)):
    return ref_service.update_cluster(db, cluster_id, payload)


@router.delete("/clusters/{cluster_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cluster(cluster_id: int, db: Session = Depends(get_db)):
    ref_service.delete_cluster(db, cluster_id)


# ── Categories CRUD ───────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    return ref_service.get_categories(db)


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    return ref_service.create_category(db, payload)


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(category_id: int, db: Session = Depends(get_db)):
    return ref_service.get_category(db, category_id)


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)):
    return ref_service.update_category(db, category_id, payload)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    ref_service.delete_category(db, category_id)


# ── TestCases CRUD ────────────────────────────────────────────────────────────

@router.get("/testcases", response_model=list[TestCaseResponse])
def list_testcases(category_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    return ref_service.get_testcases(db, category_id)


@router.post("/testcases", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
def create_testcase(payload: TestCaseCreate, db: Session = Depends(get_db)):
    return ref_service.create_testcase(db, payload)


@router.get("/testcases/{testcase_id}", response_model=TestCaseResponse)
def get_testcase(testcase_id: int, db: Session = Depends(get_db)):
    return ref_service.get_testcase(db, testcase_id)


@router.put("/testcases/{testcase_id}", response_model=TestCaseResponse)
def update_testcase(testcase_id: int, payload: TestCaseUpdate, db: Session = Depends(get_db)):
    return ref_service.update_testcase(db, testcase_id, payload)


@router.delete("/testcases/{testcase_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_testcase(testcase_id: int, db: Session = Depends(get_db)):
    ref_service.delete_testcase(db, testcase_id)


# ── Environments ──────────────────────────────────────────────────────────────

@router.get("/envs", response_model=list[str])
def list_envs(db: Session = Depends(get_db)):
    """Returns ordered list of environment names for frontend dropdowns."""
    return ref_service.get_environment_names(db)


@router.post("/envs", response_model=EnvironmentResponse, status_code=status.HTTP_201_CREATED)
def create_env(payload: EnvironmentCreate, db: Session = Depends(get_db)):
    from app.models.environment import Environment
    env = Environment(**payload.model_dump())
    db.add(env)
    db.commit()
    db.refresh(env)
    return env
