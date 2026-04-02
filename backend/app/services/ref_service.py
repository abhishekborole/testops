from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.location import Location
from app.models.cluster import Cluster
from app.models.category import Category
from app.models.testcase import TestCase
from app.models.environment import Environment
from app.schemas.ref import (
    LocationCreate, LocationUpdate,
    ClusterCreate, ClusterUpdate,
    CategoryCreate, CategoryUpdate,
    TestCaseCreate, TestCaseUpdate,
    CategoryWithTests, LocationWithClusters,
)


# ── Locations ─────────────────────────────────────────────────────────────────

def get_locations(db: Session) -> list[Location]:
    return db.query(Location).options(joinedload(Location.clusters)).order_by(Location.code).all()


def get_location(db: Session, location_id: int) -> Location:
    loc = db.query(Location).options(joinedload(Location.clusters)).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return loc


def create_location(db: Session, payload: LocationCreate) -> Location:
    loc = Location(**payload.model_dump())
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


def update_location(db: Session, location_id: int, payload: LocationUpdate) -> Location:
    loc = get_location(db, location_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(loc, k, v)
    db.commit()
    db.refresh(loc)
    return loc


def delete_location(db: Session, location_id: int) -> None:
    loc = get_location(db, location_id)
    db.delete(loc)
    db.commit()


def get_locations_map(db: Session) -> dict:
    """Returns data in the same shape as the frontend LOCS constant."""
    locs = get_locations(db)
    return {
        loc.code: {"label": loc.label, "clusters": [c.name for c in loc.clusters]}
        for loc in locs
    }


# ── Clusters ──────────────────────────────────────────────────────────────────

def get_clusters(db: Session, location_id: int | None = None) -> list[Cluster]:
    q = db.query(Cluster)
    if location_id:
        q = q.filter(Cluster.location_id == location_id)
    return q.order_by(Cluster.name).all()


def get_cluster(db: Session, cluster_id: int) -> Cluster:
    c = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    return c


def create_cluster(db: Session, payload: ClusterCreate) -> Cluster:
    cluster = Cluster(**payload.model_dump())
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


def update_cluster(db: Session, cluster_id: int, payload: ClusterUpdate) -> Cluster:
    cluster = get_cluster(db, cluster_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cluster, k, v)
    db.commit()
    db.refresh(cluster)
    return cluster


def delete_cluster(db: Session, cluster_id: int) -> None:
    cluster = get_cluster(db, cluster_id)
    db.delete(cluster)
    db.commit()


# ── Categories ────────────────────────────────────────────────────────────────

def get_categories(db: Session) -> list[Category]:
    return (
        db.query(Category)
        .options(joinedload(Category.test_cases))
        .order_by(Category.display_order)
        .all()
    )


def get_category(db: Session, category_id: int) -> Category:
    cat = db.query(Category).options(joinedload(Category.test_cases)).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return cat


def create_category(db: Session, payload: CategoryCreate) -> Category:
    cat = Category(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def update_category(db: Session, category_id: int, payload: CategoryUpdate) -> Category:
    cat = get_category(db, category_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, category_id: int) -> None:
    cat = get_category(db, category_id)
    db.delete(cat)
    db.commit()


def get_categories_flat(db: Session) -> list[CategoryWithTests]:
    """Returns data in the same shape as the frontend CATS constant."""
    cats = get_categories(db)
    return [
        CategoryWithTests(
            id=cat.slug,
            name=cat.name,
            critical=cat.is_critical,
            tests=[tc.name for tc in cat.test_cases],
        )
        for cat in cats
    ]


# ── TestCases ─────────────────────────────────────────────────────────────────

def get_testcases(db: Session, category_id: int | None = None) -> list[TestCase]:
    q = db.query(TestCase)
    if category_id:
        q = q.filter(TestCase.category_id == category_id)
    return q.order_by(TestCase.category_id, TestCase.display_order).all()


def get_testcase(db: Session, testcase_id: int) -> TestCase:
    tc = db.query(TestCase).filter(TestCase.id == testcase_id).first()
    if not tc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TestCase not found")
    return tc


def create_testcase(db: Session, payload: TestCaseCreate) -> TestCase:
    tc = TestCase(**payload.model_dump())
    db.add(tc)
    db.commit()
    db.refresh(tc)
    return tc


def update_testcase(db: Session, testcase_id: int, payload: TestCaseUpdate) -> TestCase:
    tc = get_testcase(db, testcase_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tc, k, v)
    db.commit()
    db.refresh(tc)
    return tc


def delete_testcase(db: Session, testcase_id: int) -> None:
    tc = get_testcase(db, testcase_id)
    db.delete(tc)
    db.commit()


# ── Environments ──────────────────────────────────────────────────────────────

def get_environments(db: Session) -> list[Environment]:
    return db.query(Environment).order_by(Environment.display_order).all()


def get_environment_names(db: Session) -> list[str]:
    return [e.name for e in get_environments(db)]
