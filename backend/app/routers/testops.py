"""
TestOps execution router
POST /api/testops/{category}/execute
GET  /api/testops/categories
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.schemas.testops import ExecuteRequest, ExecuteResponse
from app.services import testops_service

router = APIRouter(prefix="/testops", tags=["TestOps Execution"])


@router.get("/categories", summary="List available test categories")
def list_categories() -> dict:
    """Return all supported category slugs with their JSON names and executor class."""
    return testops_service.list_categories()


@router.post(
    "/{category}/execute",
    response_model=ExecuteResponse,
    summary="Execute test cases for a category against an OpenShift cluster",
)
async def execute_category(
    category: str,
    payload: ExecuteRequest,
) -> ExecuteResponse:
    """
    Execute test cases for the specified category against a live OpenShift cluster.

    **category** examples: `cluster-health`, `networking`, `storage`, `vm-operations`,
    `migrations`, `integration`, `backup-restore`, `compliance`, `monitoring`,
    `security`, `hardware`

    If `test_ids` is omitted, all tests in the category are executed.
    """
    return await testops_service.execute_category(
        category_slug=category,
        request=payload,
        json_path=settings.TESTCASES_JSON_PATH,
    )
