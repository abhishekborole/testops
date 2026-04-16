"""
TestOps Execution Service
Loads testcases.json, filters by category/test_ids, dispatches to executor, aggregates results.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status

from app.executors.base import OpenShiftClient
from app.executors.cluster_health   import ClusterHealthExecutor
from app.executors.networking       import NetworkingExecutor
from app.executors.storage          import StorageExecutor
from app.executors.vm_operations    import VMOperationsExecutor
from app.executors.migrations       import MigrationsExecutor
from app.executors.integration      import IntegrationExecutor
from app.executors.backup_restore   import BackupRestoreExecutor
from app.executors.compliance       import ComplianceExecutor
from app.executors.monitoring_logging import MonitoringLoggingExecutor
from app.executors.security_access  import SecurityAccessExecutor
from app.executors.hardware         import HardwareExecutor
from app.schemas.testops import (
    ExecuteRequest,
    ExecuteResponse,
    Summary,
    TestResult as TestResultSchema,
)

# ── Category registry ─────────────────────────────────────────────────────────
# Maps URL slug → (JSON category name, executor class)
CATEGORY_REGISTRY: dict[str, tuple[str, type]] = {
    "cluster-health":  ("Cluster Health & Core Services", ClusterHealthExecutor),
    "networking":      ("Networking",                     NetworkingExecutor),
    "storage":         ("Storage",                        StorageExecutor),
    "vm-operations":   ("VM Operations",                  VMOperationsExecutor),
    "migrations":      ("Migrations",                     MigrationsExecutor),
    "integration":     ("Integration",                    IntegrationExecutor),
    "backup-restore":  ("Backup & Restore",               BackupRestoreExecutor),
    "compliance":      ("Compliance & Policy",            ComplianceExecutor),
    "monitoring":      ("Monitoring & Logging",           MonitoringLoggingExecutor),
    "security":        ("Security & Access",              SecurityAccessExecutor),
    "hardware":        ("Hardware",                       HardwareExecutor),
}

# ── JSON loader (cached at module level after first read) ─────────────────────
_testcases_cache: Optional[dict] = None


def _load_testcases(json_path: str) -> dict:
    global _testcases_cache
    if _testcases_cache is None:
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"testcases.json not found at: {path.resolve()}")
        with path.open(encoding="utf-8") as f:
            _testcases_cache = json.load(f)
    return _testcases_cache


def _find_category(data: dict, category_name: str) -> Optional[dict]:
    for cat in data.get("categories", []):
        if cat["category"].lower().strip() == category_name.lower().strip():
            return cat
    return None


def _build_summary(results: list) -> Summary:
    total      = len(results)
    passed     = sum(1 for r in results if r.status == "Passed")
    failed     = sum(1 for r in results if r.status == "Failed")
    blocked    = sum(1 for r in results if r.status == "Blocked")
    in_progress = sum(1 for r in results if r.status == "In Progress")
    return Summary(
        total=total,
        passed=passed,
        failed=failed,
        blocked=blocked,
        in_progress=in_progress,
    )


# ── Main execution entry point ────────────────────────────────────────────────

async def execute_category(
    category_slug: str,
    request: ExecuteRequest,
    json_path: str,
) -> ExecuteResponse:
    # 1. Validate category slug
    if category_slug not in CATEGORY_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Category '{category_slug}' not found. "
                f"Available: {list(CATEGORY_REGISTRY.keys())}"
            ),
        )

    category_name, ExecutorClass = CATEGORY_REGISTRY[category_slug]

    # 2. Load testcases.json
    try:
        data = _load_testcases(json_path)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    # 3. Find category in JSON
    cat_data = _find_category(data, category_name)
    if cat_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category_name}' not found in testcases.json.",
        )

    # 4. Filter test cases
    all_tcs = cat_data.get("test_cases", [])
    if request.test_ids:
        tcs = [tc for tc in all_tcs if tc["id"] in request.test_ids]
        missing = set(request.test_ids) - {tc["id"] for tc in tcs}
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Test IDs not found in category '{category_name}': {sorted(missing)}",
            )
    else:
        tcs = all_tcs

    if not tcs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No test cases available in category '{category_name}'.",
        )

    # 5. Execute
    started_at = datetime.now(timezone.utc)
    executor   = ExecutorClass()
    results    = []

    async with OpenShiftClient(
        cluster_api_url=request.cluster_api_url,
        auth_token=request.auth_token,
        skip_tls_verify=request.skip_tls_verify,
    ) as client:
        for tc in tcs:
            result = await executor.execute(tc, client)
            results.append(result)

    completed_at = datetime.now(timezone.utc)

    # 6. Build response
    result_schemas = [
        TestResultSchema(
            id=r.id,
            test_case=r.test_case,
            status=r.status,
            failure_details=r.failure_details,
            evidence=r.evidence,
        )
        for r in results
    ]

    return ExecuteResponse(
        run_id=request.run_id,
        cluster_name=request.cluster_name,
        category=category_name,
        environment=request.environment,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        summary=_build_summary(result_schemas),
        results=result_schemas,
    )


def list_categories() -> dict:
    """Return available categories and their test counts (requires json_path)."""
    return {
        slug: {"category": name, "executor": cls.__name__}
        for slug, (name, cls) in CATEGORY_REGISTRY.items()
    }
