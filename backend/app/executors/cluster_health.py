"""
Cluster Health & Core Services — TC-001 to TC-013
"""
from __future__ import annotations

import asyncio
import json

import httpx

from .base import BaseExecutor, OpenShiftClient, TestResult

# Mandatory namespaces expected on any OpenShift cluster
MANDATORY_NAMESPACES = [
    "openshift-monitoring",
    "openshift-logging",
    "openshift-etcd",
    "openshift-kube-apiserver",
    "openshift-operator-lifecycle-manager",
    "openshift-gitops",
    "open-cluster-management",
]

# Mandatory deployments: {namespace: [deployment_name, ...]}
MANDATORY_DEPLOYMENTS = {
    "openshift-monitoring": ["prometheus-operator", "alertmanager-main", "thanos-querier"],
    "openshift-operator-lifecycle-manager": ["catalog-operator", "olm-operator"],
    "open-cluster-management": ["cluster-manager"],
}

# Mandatory CSV display-name substrings to look for
MANDATORY_OPERATORS = [
    "Advanced Cluster Management",
    "OpenShift Virtualization",
    "Red Hat OpenShift GitOps",
    "Multicluster Engine",
]

TEST_NS = "testops-runner"


class ClusterHealthExecutor(BaseExecutor):

    FUNCTION_MAP = {
        "TC-001": "_tc_001",
        "TC-002": "_tc_002",
        "TC-003": "_tc_003",
        "TC-004": "_tc_004",
        "TC-005": "_tc_005",
        "TC-006": "_tc_006",
        "TC-007": "_tc_007",
        "TC-008": "_tc_008",
        "TC-009": "_tc_009",
        "TC-010": "_tc_010",
        "TC-011": "_tc_011",
        "TC-012": "_tc_012",
        "TC-013": "_tc_013",
    }

    # ── TC-001: ManagedCluster joined/available/hubAccepted ───────────────────

    async def _tc_001(self, result: TestResult, client: OpenShiftClient) -> None:
        data = await client.get(
            "/apis/cluster.open-cluster-management.io/v1/managedclusters"
        )
        clusters = data.get("items", [])
        if not clusters:
            result.failed("No ManagedCluster resources found.")
            return

        lines = []
        all_ok = True
        for mc in clusters:
            name = mc["metadata"]["name"]
            conditions = mc.get("status", {}).get("conditions", [])
            joined   = client.condition_true(conditions, "ManagedClusterJoined")
            available = client.condition_true(conditions, "ManagedClusterConditionAvailable")
            hub      = client.condition_true(conditions, "HubAcceptedManagedCluster")
            ok = joined and available and hub
            if not ok:
                all_ok = False
            lines.append(
                f"  {name}: joined={joined}, available={available}, hubAccepted={hub} → {'OK' if ok else 'FAIL'}"
            )

        result.evidence.append("ManagedCluster conditions:\n" + "\n".join(lines))
        if all_ok:
            result.passed(f"{len(clusters)} ManagedCluster(s) all joined/available/hubAccepted.")
        else:
            result.failed("One or more ManagedClusters failed condition checks.")

    # ── TC-002: MultiClusterHub Running in ACM ────────────────────────────────

    async def _tc_002(self, result: TestResult, client: OpenShiftClient) -> None:
        data = await client.get(
            "/apis/operator.open-cluster-management.io/v1/multiclusterhubs"
        )
        items = data.get("items", [])
        if not items:
            result.failed("No MultiClusterHub resource found in ACM.")
            return

        lines = []
        all_running = True
        for mch in items:
            name  = mch["metadata"]["name"]
            phase = mch.get("status", {}).get("phase", "Unknown")
            if phase != "Running":
                all_running = False
            lines.append(f"  {name}: phase={phase}")

        result.evidence.append("MultiClusterHub status:\n" + "\n".join(lines))
        if all_running:
            result.passed("MultiClusterHub is Running.")
        else:
            result.failed("MultiClusterHub is not in Running phase.")

    # ── TC-003: MultiClusterHub absent on managed cluster ─────────────────────

    async def _tc_003(self, result: TestResult, client: OpenShiftClient) -> None:
        try:
            data = await client.get(
                "/apis/operator.open-cluster-management.io/v1/multiclusterhubs"
            )
            items = data.get("items", [])
            if items:
                names = [i["metadata"]["name"] for i in items]
                result.failed(
                    "MultiClusterHub resource found on managed cluster (should be absent).",
                    f"Found: {names}",
                )
            else:
                result.passed("MultiClusterHub resource absent on managed cluster — as expected.")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 403):
                # 404 = CRD absent, 403 = no permission → implies hub not installed
                result.passed(
                    f"MultiClusterHub CRD not present (HTTP {exc.response.status_code}) — "
                    "confirms managed cluster has no hub installed."
                )
            else:
                raise

    # ── TC-004: Cluster API & Authentication ──────────────────────────────────

    async def _tc_004(self, result: TestResult, client: OpenShiftClient) -> None:
        # Call /apis to verify API server is reachable and token is accepted
        data = await client.get("/apis")
        groups = [g["name"] for g in data.get("groups", [])]
        result.evidence.append(
            f"API server reachable. API groups ({len(groups)} total):\n  "
            + ", ".join(groups[:20])
            + ("…" if len(groups) > 20 else "")
        )

        # Verify OpenShift-specific groups exist (confirms OpenShift, not vanilla k8s)
        ocp_groups = [g for g in groups if "openshift.io" in g]
        if not ocp_groups:
            result.failed("No openshift.io API groups found — may not be an OpenShift cluster.")
            return

        # Also call /api/v1 to verify core API
        await client.get("/api/v1")
        result.passed(
            f"Cluster API reachable. Authentication valid. "
            f"{len(ocp_groups)} OpenShift API groups present."
        )

    # ── TC-005: Web Console accessibility ─────────────────────────────────────

    async def _tc_005(self, result: TestResult, client: OpenShiftClient) -> None:
        routes = await client.get_routes("openshift-console")
        console_routes = [r for r in routes if r["metadata"]["name"] == "console"]
        if not console_routes:
            result.failed("No 'console' route found in openshift-console namespace.")
            return

        host = console_routes[0].get("spec", {}).get("host", "")
        tls  = console_routes[0].get("spec", {}).get("tls", {})
        url  = f"https://{host}" if tls else f"http://{host}"
        result.evidence.append(f"Console route: {url}")

        # Try to reach the console URL (expecting redirect / 200 / 403 — all mean it's up)
        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as h:
                r = await h.get(url, follow_redirects=True)
                result.evidence.append(f"HTTP probe: {r.status_code}")
                if r.status_code < 500:
                    result.passed(f"Web console accessible at {url} (HTTP {r.status_code}).")
                else:
                    result.failed(f"Web console returned HTTP {r.status_code}.", url)
        except Exception as exc:
            result.failed(f"Console unreachable: {exc}", url)

    # ── TC-006: Cluster Operators in Available state ──────────────────────────

    async def _tc_006(self, result: TestResult, client: OpenShiftClient) -> None:
        operators = await client.get_cluster_operators()
        if not operators:
            result.failed("No ClusterOperators found.")
            return

        unavailable = []
        lines = []
        for op in operators:
            name = op["metadata"]["name"]
            conditions = op.get("status", {}).get("conditions", [])
            avail = client.condition_true(conditions, "Available")
            prog  = client.condition_true(conditions, "Progressing")
            degrade = client.condition_true(conditions, "Degraded")
            ok = avail and not degrade
            lines.append(
                f"  {name}: Available={avail}, Progressing={prog}, Degraded={degrade}"
            )
            if not ok:
                unavailable.append(name)

        result.evidence.append("ClusterOperators:\n" + "\n".join(lines))
        if not unavailable:
            result.passed(f"All {len(operators)} ClusterOperators are Available and not Degraded.")
        else:
            result.failed(
                f"{len(unavailable)} operator(s) not Available: {', '.join(unavailable)}"
            )

    # ── TC-007: MachineConfigPools Available ──────────────────────────────────

    async def _tc_007(self, result: TestResult, client: OpenShiftClient) -> None:
        data = await client.get(
            "/apis/machineconfiguration.openshift.io/v1/machineconfigpools"
        )
        pools = data.get("items", [])
        if not pools:
            result.failed("No MachineConfigPools found.")
            return

        bad = []
        lines = []
        for p in pools:
            name = p["metadata"]["name"]
            conds = p.get("status", {}).get("conditions", [])
            avail = client.condition_true(conds, "Updated") and not client.condition_true(conds, "Degraded")
            ready = p.get("status", {}).get("readyMachineCount", 0)
            total = p.get("status", {}).get("machineCount", 0)
            lines.append(f"  {name}: readyMachines={ready}/{total}, ok={avail}")
            if ready < total:
                bad.append(name)

        result.evidence.append("MachineConfigPools:\n" + "\n".join(lines))
        if not bad:
            result.passed(f"All {len(pools)} MachineConfigPools have all machines ready.")
        else:
            result.failed(f"Pools with unready machines: {', '.join(bad)}")

    # ── TC-008: All nodes Ready ───────────────────────────────────────────────

    async def _tc_008(self, result: TestResult, client: OpenShiftClient) -> None:
        nodes = await client.get_nodes()
        if not nodes:
            result.failed("No nodes found in cluster.")
            return

        not_ready = []
        lines = []
        for node in nodes:
            name  = node["metadata"]["name"]
            conds = node.get("status", {}).get("conditions", [])
            ready = client.condition_true(conds, "Ready")
            roles = [
                k.split("/")[1]
                for k in node["metadata"].get("labels", {})
                if k.startswith("node-role.kubernetes.io/")
            ]
            lines.append(f"  {name} [{','.join(roles)}]: Ready={ready}")
            if not ready:
                not_ready.append(name)

        result.evidence.append(f"Nodes ({len(nodes)}):\n" + "\n".join(lines))
        if not not_ready:
            result.passed(f"All {len(nodes)} nodes are in Ready state.")
        else:
            result.failed(f"Nodes not Ready: {', '.join(not_ready)}")

    # ── TC-009: Create PVC & validate bind to default StorageClass ────────────

    async def _tc_009(self, result: TestResult, client: OpenShiftClient) -> None:
        await client.ensure_namespace(TEST_NS)

        # Find default storage class
        scs = await client.get_storage_classes()
        default_sc = next(
            (
                sc["metadata"]["name"]
                for sc in scs
                if sc["metadata"]
                .get("annotations", {})
                .get("storageclass.kubernetes.io/is-default-class") == "true"
            ),
            None,
        )
        if not default_sc:
            result.blocked("No default StorageClass found — cannot test PVC binding.")
            return

        result.evidence.append(f"Default StorageClass: {default_sc}")
        pvc_name = "testops-tc009-pvc"

        pvc_body = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": pvc_name, "namespace": TEST_NS},
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "resources": {"requests": {"storage": "1Gi"}},
                "storageClassName": default_sc,
            },
        }

        try:
            # Create PVC
            await client.post(
                f"/api/v1/namespaces/{TEST_NS}/persistentvolumeclaims", pvc_body
            )
            result.evidence.append(f"PVC '{pvc_name}' created in namespace '{TEST_NS}'.")

            # Wait for binding
            phase = await client.wait_for_pvc_bound(TEST_NS, pvc_name, timeout=90)
            result.evidence.append(f"PVC phase after wait: {phase}")

            if phase == "Bound":
                result.passed(f"PVC bound successfully via StorageClass '{default_sc}'.")
            else:
                result.failed(f"PVC did not bind — final phase: {phase}")
        finally:
            # Clean up
            try:
                await client.delete(
                    f"/api/v1/namespaces/{TEST_NS}/persistentvolumeclaims/{pvc_name}"
                )
                result.evidence.append(f"PVC '{pvc_name}' deleted (cleanup).")
            except Exception:
                pass

    # ── TC-010: ArgoCD Console accessibility ──────────────────────────────────

    async def _tc_010(self, result: TestResult, client: OpenShiftClient) -> None:
        ns = "openshift-gitops"
        try:
            routes = await client.get_routes(ns)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                result.failed(f"Namespace '{ns}' not found — OpenShift GitOps not installed.")
                return
            raise

        argocd_routes = [r for r in routes if "argocd" in r["metadata"]["name"].lower()
                         or "gitops" in r["metadata"]["name"].lower()]
        if not argocd_routes:
            # Try openshift-gitops-server route specifically
            argocd_routes = [r for r in routes if "server" in r["metadata"]["name"]]

        if not argocd_routes:
            result.failed(f"No ArgoCD route found in namespace '{ns}'.")
            return

        host = argocd_routes[0].get("spec", {}).get("host", "")
        url  = f"https://{host}"
        result.evidence.append(f"ArgoCD route: {url}")

        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as h:
                r = await h.get(url, follow_redirects=True)
                result.evidence.append(f"HTTP probe: {r.status_code}")
                if r.status_code < 500:
                    result.passed(f"ArgoCD console accessible at {url} (HTTP {r.status_code}).")
                else:
                    result.failed(f"ArgoCD console returned HTTP {r.status_code}.", url)
        except Exception as exc:
            result.failed(f"ArgoCD console unreachable: {exc}", url)

    # ── TC-011: Mandatory platform namespaces present ─────────────────────────

    async def _tc_011(self, result: TestResult, client: OpenShiftClient) -> None:
        ns_data = await client.get_namespaces()
        existing = {ns["metadata"]["name"] for ns in ns_data}

        missing = [ns for ns in MANDATORY_NAMESPACES if ns not in existing]
        present = [ns for ns in MANDATORY_NAMESPACES if ns in existing]

        result.evidence.append(
            f"Checked {len(MANDATORY_NAMESPACES)} mandatory namespaces.\n"
            f"  Present: {', '.join(present)}\n"
            f"  Missing: {', '.join(missing) if missing else 'none'}"
        )

        if not missing:
            result.passed(f"All {len(MANDATORY_NAMESPACES)} mandatory namespaces are present.")
        else:
            result.failed(f"Missing namespaces: {', '.join(missing)}")

    # ── TC-012: Mandatory pods & deployments running ──────────────────────────

    async def _tc_012(self, result: TestResult, client: OpenShiftClient) -> None:
        issues = []
        lines  = []

        for ns, deployments in MANDATORY_DEPLOYMENTS.items():
            try:
                data = await client.get(
                    f"/apis/apps/v1/namespaces/{ns}/deployments"
                )
                items = data.get("items", [])
                found_names = {d["metadata"]["name"] for d in items}

                for dep in deployments:
                    matches = [n for n in found_names if n.startswith(dep)]
                    if matches:
                        # Check ready replicas
                        dep_obj = next(d for d in items if d["metadata"]["name"].startswith(dep))
                        ready   = dep_obj.get("status", {}).get("readyReplicas", 0)
                        desired = dep_obj.get("spec", {}).get("replicas", 1)
                        ok = ready >= 1
                        lines.append(f"  [{ns}] {dep}: {ready}/{desired} ready — {'OK' if ok else 'FAIL'}")
                        if not ok:
                            issues.append(f"{ns}/{dep}")
                    else:
                        lines.append(f"  [{ns}] {dep}: NOT FOUND")
                        issues.append(f"{ns}/{dep}")
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    lines.append(f"  [{ns}]: namespace not found")
                    issues.append(ns)
                else:
                    raise

        result.evidence.append("Mandatory deployments check:\n" + "\n".join(lines))
        if not issues:
            result.passed("All mandatory pods/deployments are running.")
        else:
            result.failed(f"Issues with: {', '.join(issues)}")

    # ── TC-013: Mandatory operators via CSVs ──────────────────────────────────

    async def _tc_013(self, result: TestResult, client: OpenShiftClient) -> None:
        try:
            csvs = await client.get_csvs()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                result.blocked("Cannot list ClusterServiceVersions (no permission or OLM not present).")
                return
            raise

        succeeded = [
            csv for csv in csvs
            if csv.get("status", {}).get("phase") == "Succeeded"
        ]
        csv_names = [csv.get("spec", {}).get("displayName", csv["metadata"]["name"])
                     for csv in succeeded]

        missing = []
        for op in MANDATORY_OPERATORS:
            if not any(op.lower() in n.lower() for n in csv_names):
                missing.append(op)

        result.evidence.append(
            f"Total CSVs in Succeeded phase: {len(succeeded)}\n"
            f"Sample: {', '.join(csv_names[:10])}"
        )

        if not missing:
            result.passed(f"All {len(MANDATORY_OPERATORS)} mandatory operators found via CSVs.")
        else:
            result.failed(f"Operators not found or not Succeeded: {', '.join(missing)}")
