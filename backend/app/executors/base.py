"""
OpenShiftClient  — async httpx wrapper around the k8s/OpenShift REST API.
BaseExecutor     — dispatch layer every category executor inherits from.
TestResult       — mutable dataclass used by every executor function.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx


# ── Result ───────────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    id: str
    test_case: str
    status: str = "Blocked"          # Passed | Failed | Blocked | In Progress
    failure_details: str = ""
    evidence: list[str] = field(default_factory=list)

    def passed(self, msg: str = "") -> None:
        self.status = "Passed"
        if msg:
            self.evidence.append(msg)

    def failed(self, reason: str, evidence: str = "") -> None:
        self.status = "Failed"
        self.failure_details = reason
        if evidence:
            self.evidence.append(evidence)

    def blocked(self, reason: str) -> None:
        self.status = "Blocked"
        self.failure_details = reason


# ── OpenShift / k8s REST client ──────────────────────────────────────────────

class OpenShiftClient:
    """Thin async wrapper around the Kubernetes / OpenShift REST API."""

    def __init__(
        self,
        cluster_api_url: str,
        auth_token: Optional[str] = None,
        skip_tls_verify: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = cluster_api_url.rstrip("/")
        self.auth_token = auth_token
        self.skip_tls_verify = skip_tls_verify
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "OpenShiftClient":
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            verify=not self.skip_tls_verify,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()

    # ── raw verbs ────────────────────────────────────────────────────────────

    async def get(self, path: str, **kwargs: Any) -> dict:
        r = await self._client.get(path, **kwargs)
        r.raise_for_status()
        return r.json()

    async def post(self, path: str, body: dict, **kwargs: Any) -> dict:
        r = await self._client.post(path, json=body, **kwargs)
        r.raise_for_status()
        return r.json()

    async def put(self, path: str, body: dict, **kwargs: Any) -> dict:
        r = await self._client.put(path, json=body, **kwargs)
        r.raise_for_status()
        return r.json()

    async def patch(
        self,
        path: str,
        body: dict,
        content_type: str = "application/strategic-merge-patch+json",
        **kwargs: Any,
    ) -> dict:
        r = await self._client.patch(
            path, json=body,
            headers={"Content-Type": content_type},
            **kwargs,
        )
        r.raise_for_status()
        return r.json()

    async def delete(self, path: str, **kwargs: Any) -> dict:
        r = await self._client.delete(path, **kwargs)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {}

    async def exists(self, path: str) -> tuple[bool, dict]:
        """Return (found, body). Does not raise on 404."""
        try:
            body = await self.get(path)
            return True, body
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False, {}
            raise

    # ── convenience helpers ──────────────────────────────────────────────────

    async def get_nodes(self) -> list[dict]:
        data = await self.get("/api/v1/nodes")
        return data.get("items", [])

    async def get_pods(self, namespace: Optional[str] = None) -> list[dict]:
        path = (
            f"/api/v1/namespaces/{namespace}/pods"
            if namespace
            else "/api/v1/pods"
        )
        data = await self.get(path)
        return data.get("items", [])

    async def get_pvcs(self, namespace: Optional[str] = None) -> list[dict]:
        path = (
            f"/api/v1/namespaces/{namespace}/persistentvolumeclaims"
            if namespace
            else "/api/v1/persistentvolumeclaims"
        )
        data = await self.get(path)
        return data.get("items", [])

    async def get_namespaces(self) -> list[dict]:
        data = await self.get("/api/v1/namespaces")
        return data.get("items", [])

    async def get_storage_classes(self) -> list[dict]:
        data = await self.get("/apis/storage.k8s.io/v1/storageclasses")
        return data.get("items", [])

    async def get_cluster_operators(self) -> list[dict]:
        data = await self.get("/apis/config.openshift.io/v1/clusteroperators")
        return data.get("items", [])

    async def get_routes(self, namespace: str) -> list[dict]:
        data = await self.get(
            f"/apis/route.openshift.io/v1/namespaces/{namespace}/routes"
        )
        return data.get("items", [])

    async def get_csvs(self, namespace: Optional[str] = None) -> list[dict]:
        path = (
            f"/apis/operators.coreos.com/v1alpha1/namespaces/{namespace}/clusterserviceversions"
            if namespace
            else "/apis/operators.coreos.com/v1alpha1/clusterserviceversions"
        )
        data = await self.get(path)
        return data.get("items", [])

    async def ensure_namespace(self, name: str) -> None:
        """Create namespace if it doesn't exist."""
        found, _ = await self.exists(f"/api/v1/namespaces/{name}")
        if not found:
            await self.post(
                "/api/v1/namespaces",
                {"apiVersion": "v1", "kind": "Namespace",
                 "metadata": {"name": name}},
            )

    async def wait_for_pvc_bound(
        self, namespace: str, name: str, timeout: int = 60
    ) -> str:
        """Poll PVC phase until Bound or timeout. Returns final phase."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            data = await self.get(
                f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{name}"
            )
            phase = data.get("status", {}).get("phase", "Pending")
            if phase in ("Bound", "Lost"):
                return phase
            await asyncio.sleep(3)
        return "Timeout"

    # ── condition helpers ────────────────────────────────────────────────────

    @staticmethod
    def condition_true(conditions: list[dict], ctype: str) -> bool:
        for c in conditions:
            if c.get("type") == ctype:
                return c.get("status") == "True"
        return False

    @staticmethod
    def fmt_items(items: list[dict], name_path: str = "metadata.name") -> str:
        names = []
        for item in items:
            obj = item
            for key in name_path.split("."):
                obj = obj.get(key, {}) if isinstance(obj, dict) else {}
            if isinstance(obj, str):
                names.append(obj)
        return ", ".join(names) if names else "(none)"


# ── Base executor ─────────────────────────────────────────────────────────────

class BaseExecutor:
    """
    Subclass this for each test category.

    FUNCTION_MAP = {"TC-NNN": "_tc_NNN"}   # maps test-case ID → method name
    """

    FUNCTION_MAP: dict[str, str] = {}

    async def execute(self, tc: dict, client: OpenShiftClient) -> TestResult:
        result = TestResult(id=tc["id"], test_case=tc["test_case"])
        fn_name = self.FUNCTION_MAP.get(tc["id"])

        if not fn_name:
            result.blocked("No executor function registered for this test case ID.")
            return result

        fn = getattr(self, fn_name, None)
        if fn is None:
            result.blocked(f"Method '{fn_name}' not implemented in {type(self).__name__}.")
            return result

        try:
            await fn(result, client)
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            body = exc.response.text[:400]
            result.failed(
                f"HTTP {code} from cluster API",
                f"GET/POST {exc.request.url}\nHTTP {code}\n{body}",
            )
        except httpx.RequestError as exc:
            result.failed(f"Network error: {exc}")
        except asyncio.TimeoutError:
            result.failed("Operation timed out waiting for cluster response.")
        except Exception as exc:
            result.failed(f"Unexpected error: {type(exc).__name__}: {exc}")

        return result
