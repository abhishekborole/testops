from pydantic import BaseModel, field_validator
from typing import Optional, List


class ExecuteRequest(BaseModel):
    cluster_name: str
    cluster_api_url: str
    auth_token: Optional[str] = None
    test_ids: Optional[List[str]] = None  # None = run all in category
    run_id: str
    environment: str = "prod"
    skip_tls_verify: bool = True

    @field_validator("cluster_api_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


class TestResult(BaseModel):
    id: str
    test_case: str
    status: str  # Passed | Failed | Blocked | In Progress
    failure_details: str = ""
    evidence: List[str] = []


class Summary(BaseModel):
    total: int
    passed: int
    failed: int
    blocked: int
    in_progress: int


class ExecuteResponse(BaseModel):
    run_id: str
    cluster_name: str
    category: str
    environment: str
    started_at: str
    completed_at: str
    summary: Summary
    results: List[TestResult]
